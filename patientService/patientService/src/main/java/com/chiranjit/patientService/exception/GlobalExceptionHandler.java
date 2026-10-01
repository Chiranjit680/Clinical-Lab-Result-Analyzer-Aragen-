package com.chiranjit.patientService.exception;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.multipart.MaxUploadSizeExceededException;

import java.util.Map;

@RestControllerAdvice
public class GlobalExceptionHandler {

	/**
	 * Without this the container surfaces a raw 500 when a file exceeds
	 * spring.servlet.multipart.max-file-size, which reads as a server bug
	 * rather than a rejected upload.
	 */
	@ExceptionHandler(MaxUploadSizeExceededException.class)
	@ResponseStatus(HttpStatus.PAYLOAD_TOO_LARGE)
	public Map<String, String> handleUploadTooLarge(MaxUploadSizeExceededException ex) {
		return Map.of("error", "That file is larger than the upload limit.");
	}

}
