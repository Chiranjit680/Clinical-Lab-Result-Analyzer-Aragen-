package com.chiranjit.patientService.service;

import jakarta.annotation.PostConstruct;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.Resource;
import org.springframework.core.io.UrlResource;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.util.StringUtils;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.web.server.ResponseStatusException;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardCopyOption;
import java.time.LocalDate;
import java.time.format.DateTimeFormatter;
import java.util.UUID;

/**
 * Writes uploaded report files to the local filesystem and hands back a path
 * relative to the upload root, which is what LabReport.reportPath stores.
 *
 * Only relative paths ever reach the database, so the upload directory can be
 * moved or remounted without rewriting existing rows.
 */
@Service
public class StorageService {

	/** Separates the generated id from the original name. A UUID contains '-' but never '_'. */
	private static final String NAME_SEPARATOR = "__";

	private static final DateTimeFormatter FOLDER = DateTimeFormatter.ofPattern("yyyy/MM");

	private final Path root;

	public StorageService(@Value("${app.upload-dir:uploads}") String uploadDir) {
		this.root = Paths.get(uploadDir).toAbsolutePath().normalize();
	}

	@PostConstruct
	void createRoot() {
		try {
			Files.createDirectories(root);
		}
		catch (IOException ex) {
			throw new IllegalStateException("Cannot create upload directory: " + root, ex);
		}
	}

	/** Stores the file at the upload root and returns its relative path. */
	public String store(MultipartFile file) {
		return store(file, null);
	}

	/**
	 * Stores the file under an optional category folder — "reports", "images" —
	 * so different kinds of upload stay apart on disk. The returned path is
	 * relative to the upload root and includes that folder.
	 */
	public String store(MultipartFile file, String category) {
		if (file == null || file.isEmpty()) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "No file was uploaded.");
		}

		String original = StringUtils.cleanPath(
				file.getOriginalFilename() == null ? "upload" : file.getOriginalFilename());
		// Keep only the leaf name, so a crafted "../../etc/passwd" cannot escape the root.
		String leaf = Paths.get(original).getFileName().toString();
		String safe = leaf.replaceAll("[^A-Za-z0-9._-]", "_");

		String prefix = (category == null || category.isBlank()) ? "" : category.trim() + "/";
		String relative = prefix + LocalDate.now().format(FOLDER) + "/" + UUID.randomUUID() + NAME_SEPARATOR + safe;
		Path target = root.resolve(relative).normalize();
		if (!target.startsWith(root)) {
			throw new ResponseStatusException(HttpStatus.BAD_REQUEST, "Invalid file name.");
		}

		try {
			Files.createDirectories(target.getParent());
			try (InputStream in = file.getInputStream()) {
				Files.copy(in, target, StandardCopyOption.REPLACE_EXISTING);
			}
		}
		catch (IOException ex) {
			throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not store the file.", ex);
		}

		return relative;
	}

	/** Loads a stored file, rejecting any path that resolves outside the upload root. */
	public StoredFile load(String relativePath) {
		if (!StringUtils.hasText(relativePath)) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "This report has no stored file.");
		}

		Path target = root.resolve(relativePath).normalize();
		if (!target.startsWith(root) || !Files.isReadable(target)) {
			throw new ResponseStatusException(HttpStatus.NOT_FOUND, "File not found: " + relativePath);
		}

		try {
			Resource resource = new UrlResource(target.toUri());
			String contentType = Files.probeContentType(target);
			return new StoredFile(resource, originalNameOf(target), contentType == null ? "application/octet-stream" : contentType);
		}
		catch (IOException ex) {
			throw new ResponseStatusException(HttpStatus.INTERNAL_SERVER_ERROR, "Could not read the file.", ex);
		}
	}

	/** Strips the generated id prefix so downloads keep the name the user uploaded. */
	private String originalNameOf(Path target) {
		String name = target.getFileName().toString();
		int at = name.indexOf(NAME_SEPARATOR);
		return at >= 0 ? name.substring(at + NAME_SEPARATOR.length()) : name;
	}

	public record StoredFile(Resource resource, String filename, String contentType) {
	}

}
