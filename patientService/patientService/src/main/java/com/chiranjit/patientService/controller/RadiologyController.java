package com.chiranjit.patientService.controller;

import com.chiranjit.patientService.dto.EmailReportRequest;
import com.chiranjit.patientService.dto.ImageAnalysisRequest;
import com.chiranjit.patientService.dto.ImageAnalysisResponse;
import com.chiranjit.patientService.dto.RadiologyImageResponse;
import com.chiranjit.patientService.entity.Modality;
import com.chiranjit.patientService.service.RadiologyService;
import com.chiranjit.patientService.service.StorageService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.core.io.Resource;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RequestPart;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.multipart.MultipartFile;

import java.util.List;
import java.util.Map;
import java.util.UUID;

@RestController
@RequestMapping("/api/images")
@RequiredArgsConstructor
public class RadiologyController {

	private final RadiologyService radiologyService;

	/**
	 * Uploads a radiological image against a patient. The stored path is
	 * generated server-side, so callers never choose where the file lands.
	 */
	@PostMapping(value = "/upload", consumes = MediaType.MULTIPART_FORM_DATA_VALUE)
	@ResponseStatus(HttpStatus.CREATED)
	public RadiologyImageResponse uploadImage(@RequestPart("file") MultipartFile file,
			@RequestParam("patientId") UUID patientId,
			@RequestParam(value = "modality", defaultValue = "OTHER") Modality modality,
			@RequestParam(value = "bodyPart", required = false) String bodyPart,
			@RequestParam(value = "description", required = false) String description) {

		return radiologyService.saveImage(file, patientId, modality, bodyPart, description);
	}

	@GetMapping("/get/{imageId}")
	public RadiologyImageResponse getImage(@PathVariable UUID imageId) {
		return radiologyService.getImage(imageId);
	}

	@GetMapping("/getall/{patientId}")
	public List<RadiologyImageResponse> getAllImages(@PathVariable UUID patientId) {
		return radiologyService.getAllImagesByPatientId(patientId);
	}

	@GetMapping("/download/{imageId}")
	public ResponseEntity<Resource> downloadImage(@PathVariable UUID imageId) {
		StorageService.StoredFile stored = radiologyService.loadImageFile(imageId);

		return ResponseEntity.ok()
				.contentType(MediaType.parseMediaType(stored.contentType()))
				// inline so PNG and JPEG preview in the browser rather than
				// forcing a download; DICOM will still download, having no
				// viewer.
				.header(HttpHeaders.CONTENT_DISPOSITION, "inline; filename=\"" + stored.filename() + "\"")
				.body(stored.resource());
	}

	/**
	 * Stores the result of a VLM run against this image, replacing any previous
	 * one.
	 *
	 * PUT, not POST: the body is the complete analysis for this image and the
	 * unique constraint on image_id makes writing it twice indistinguishable
	 * from writing it once.
	 *
	 * The run itself happens in the browser, against the agent service. It takes
	 * minutes, which is too long to hold an HTTP request open through here.
	 */
	@PutMapping("/{imageId}/analysis")
	public ImageAnalysisResponse saveAnalysis(@PathVariable UUID imageId,
			@Valid @RequestBody ImageAnalysisRequest request) {

		return radiologyService.saveAnalysis(imageId, request);
	}

	@GetMapping("/{imageId}/analysis")
	public ImageAnalysisResponse getAnalysis(@PathVariable UUID imageId) {
		return radiologyService.getAnalysis(imageId);
	}

	/** Emails this image, with its stored analysis rendered into the body. */
	@PostMapping("/{imageId}/email")
	public Map<String, String> emailImage(@PathVariable UUID imageId,
			@Valid @RequestBody EmailReportRequest request) {

		radiologyService.emailImage(imageId, request.to(), request.note());
		return Map.of("status", "sent", "to", request.to());
	}

	@DeleteMapping("/delete/{imageId}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void deleteImage(@PathVariable UUID imageId) {
		radiologyService.deleteImage(imageId);
	}

}
