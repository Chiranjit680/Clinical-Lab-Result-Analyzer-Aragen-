package com.chiranjit.patientService.service;

import com.chiranjit.patientService.dto.ImageAnalysisRequest;
import com.chiranjit.patientService.dto.ImageAnalysisResponse;
import com.chiranjit.patientService.dto.RadiologyImageResponse;
import com.chiranjit.patientService.entity.Identity;
import com.chiranjit.patientService.entity.ImageAnalysis;
import com.chiranjit.patientService.entity.Modality;
import com.chiranjit.patientService.entity.RadiologyImage;
import com.chiranjit.patientService.repository.IdentityRepository;
import com.chiranjit.patientService.repository.ImageAnalysisRepository;
import com.chiranjit.patientService.repository.RadiologyImageRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.function.Function;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class RadiologyService {

	/** Keeps images out of the reports folder on disk. */
	private static final String CATEGORY = "images";

	/**
	 * DICOM is what scanners actually produce; the rest are the formats people
	 * export to before sharing. Enforced server-side, not just in the picker,
	 * because the browser is not a trustworthy gatekeeper.
	 */
	private static final Set<String> ALLOWED_EXTENSIONS = Set.of(".dcm", ".dicom", ".png", ".jpg", ".jpeg");

	private final RadiologyImageRepository radiologyImageRepository;

	private final IdentityRepository identityRepository;

	private final StorageService storageService;

	private final ImageAnalysisRepository imageAnalysisRepository;

	private final EmailClient emailClient;

	public RadiologyImageResponse saveImage(MultipartFile file, UUID patientId, Modality modality, String bodyPart,
			String description) {

		// Resolved first so an unknown patient fails before anything is written
		// to disk, which would otherwise leave an orphaned file behind.
		Identity patient = getPatientOrThrow(patientId);
		requireSupportedType(file);

		RadiologyImage image = new RadiologyImage();
		image.setPatient(patient);
		image.setImagePath(storageService.store(file, CATEGORY));
		image.setModality(modality);
		image.setBodyPart(trimToNull(bodyPart));
		image.setDescription(trimToNull(description));
		image.setCreatedAt(Instant.now());

		return toResponse(radiologyImageRepository.save(image));
	}

	public RadiologyImageResponse getImage(UUID imageId) {
		return toResponse(getImageOrThrow(imageId));
	}

	public List<RadiologyImageResponse> getAllImagesByPatientId(UUID patientId) {
		getPatientOrThrow(patientId);
		List<RadiologyImage> images = radiologyImageRepository.findByPatientIdOrderByCreatedAtDesc(patientId);

		// One query for every analysis in the list, rather than one per image.
		Map<UUID, ImageAnalysis> byImage = imageAnalysisRepository
				.findByImageIdIn(images.stream().map(RadiologyImage::getId).toList())
				.stream()
				.collect(Collectors.toMap(analysis -> analysis.getImage().getId(), Function.identity()));

		return images.stream().map(image -> toResponse(image, byImage.get(image.getId()))).toList();
	}

	/**
	 * Stores one VLM run against an image, replacing any previous one.
	 *
	 * The replacement is enforced by the unique constraint on image_id, so an
	 * image cannot end up with two "current" analyses whatever this method does.
	 */
	public ImageAnalysisResponse saveAnalysis(UUID imageId, ImageAnalysisRequest request) {
		RadiologyImage image = getImageOrThrow(imageId);

		// Reuses the existing row when there is one, so the id a caller already
		// holds stays valid across a re-analysis.
		ImageAnalysis analysis = imageAnalysisRepository.findByImageId(imageId).orElseGet(ImageAnalysis::new);
		analysis.setImage(image);
		analysis.setQuestion(trimToNull(request.question()));
		analysis.setAnswer(request.answer());
		analysis.setModel(trimToNull(request.model()));
		analysis.setRunId(trimToNull(request.runId()));

		List<ImageAnalysisRequest.TileReport> tiles = request.tiles() == null ? List.of() : request.tiles();
		analysis.setTileCount(tiles.size());

		// Seconds on the wire, milliseconds in the column, matching duration_ms
		// on the lab analysis table.
		analysis.setDurationMs(request.seconds() == null ? null : (int) Math.round(request.seconds() * 1000));
		analysis.setPayload(toPayload(request, tiles));
		analysis.setCreatedAt(Instant.now());

		return toResponse(imageAnalysisRepository.save(analysis));
	}

	public ImageAnalysisResponse getAnalysis(UUID imageId) {
		getImageOrThrow(imageId);
		return imageAnalysisRepository.findByImageId(imageId)
				.map(this::toResponse)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND,
						"No analysis stored for image " + imageId));
	}

	/**
	 * Emails a stored image, with its latest analysis in the body.
	 *
	 * Everything the email service needs travels with the request: it has no
	 * database and cannot see the uploads folder.
	 */
	public void emailImage(UUID imageId, String to, String note) {
		RadiologyImage image = getImageOrThrow(imageId);
		StorageService.StoredFile stored = storageService.load(image.getImagePath());

		// getPatient() returns a lazy proxy. Reading its id costs nothing, but
		// reading the name would need an open session, so it is fetched outright.
		String patientName = identityRepository.findById(image.getPatient().getId())
				.map(Identity::getFullName)
				.orElse(null);

		// Null when the image has never been analysed, which is allowed.
		Map<String, Object> payload = imageAnalysisRepository.findByImageId(imageId)
				.map(ImageAnalysis::getPayload)
				.orElse(null);

		emailClient.sendImage(stored.resource(), to, patientName, caption(image), payload, note);
	}

	/** "XRAY - Chest": what the image is, for the email subject and body. */
	private static String caption(RadiologyImage image) {
		StringBuilder out = new StringBuilder(String.valueOf(image.getModality()));
		if (image.getBodyPart() != null) {
			out.append(" - ").append(image.getBodyPart());
		}
		return out.toString();
	}

	/**
	 * Rebuilds the agent service's response shape for storage.
	 *
	 * Written out field by field rather than storing the request body verbatim:
	 * what reaches the column is then exactly what this service accepted, not
	 * whatever extra keys a caller happened to post.
	 */
	private static Map<String, Object> toPayload(ImageAnalysisRequest request,
			List<ImageAnalysisRequest.TileReport> tiles) {

		List<Map<String, Object>> tilePayload = new ArrayList<>(tiles.size());
		for (ImageAnalysisRequest.TileReport tile : tiles) {
			Map<String, Object> entry = new LinkedHashMap<>();
			entry.put("tile_id", tile.tileId());
			entry.put("report", tile.report());
			tilePayload.add(entry);
		}

		// snake_case keys, so a stored payload renders with the same frontend
		// code as a live response from the agent service.
		Map<String, Object> payload = new LinkedHashMap<>();
		payload.put("answer", request.answer());
		payload.put("global_summary", request.globalSummary());
		payload.put("question", request.question());
		payload.put("model", request.model());
		payload.put("run_id", request.runId());
		payload.put("seconds", request.seconds());
		payload.put("tiles", tilePayload);
		return payload;
	}

	public StorageService.StoredFile loadImageFile(UUID imageId) {
		return storageService.load(getImageOrThrow(imageId).getImagePath());
	}

	public void deleteImage(UUID imageId) {
		// The analysis row goes with it: ON DELETE CASCADE on image_analysis.image_id.
		// The file is left on disk deliberately: deleting it
		// here would be unrecoverable, and orphan cleanup belongs in a sweep
		// that can be audited.
		radiologyImageRepository.delete(getImageOrThrow(imageId));
	}

	private void requireSupportedType(MultipartFile file) {
		String name = file == null ? null : file.getOriginalFilename();
		if (name == null || name.isBlank()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "No file was uploaded.");
		}

		String lower = name.toLowerCase(Locale.ROOT);
		boolean supported = ALLOWED_EXTENSIONS.stream().anyMatch(lower::endsWith);
		if (!supported) {
			throw new ResponseStatusException(HttpStatus.UNSUPPORTED_MEDIA_TYPE,
					"Unsupported image type. Accepted: " + String.join(", ", ALLOWED_EXTENSIONS));
		}
	}

	private RadiologyImage getImageOrThrow(UUID imageId) {
		return radiologyImageRepository.findById(imageId).orElseThrow(
				() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Image not found: " + imageId));
	}

	private Identity getPatientOrThrow(UUID patientId) {
		return identityRepository.findById(patientId).orElseThrow(
				() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Patient not found: " + patientId));
	}

	private static String trimToNull(String value) {
		if (value == null) {
			return null;
		}
		String trimmed = value.trim();
		return trimmed.isEmpty() ? null : trimmed;
	}

	private RadiologyImageResponse toResponse(RadiologyImage image) {
		return toResponse(image, imageAnalysisRepository.findByImageId(image.getId()).orElse(null));
	}

	private RadiologyImageResponse toResponse(RadiologyImage image, ImageAnalysis analysis) {
		return new RadiologyImageResponse(image.getId(), image.getPatient().getId(), image.getImagePath(),
				image.getModality(), image.getBodyPart(), image.getDescription(), image.getCreatedAt(),
				analysis != null, analysis == null ? null : analysis.getId());
	}

	private ImageAnalysisResponse toResponse(ImageAnalysis analysis) {
		return new ImageAnalysisResponse(analysis.getId(), analysis.getImage().getId(), analysis.getQuestion(),
				analysis.getAnswer(), analysis.getModel(), analysis.getRunId(), analysis.getTileCount(),
				analysis.getDurationMs(), analysis.getCreatedAt(), analysis.getPayload());
	}

}
