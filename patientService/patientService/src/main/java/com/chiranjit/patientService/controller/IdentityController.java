package com.chiranjit.patientService.controller;

import com.chiranjit.patientService.dto.IdentityRequest;
import com.chiranjit.patientService.dto.IdentityResponse;
import com.chiranjit.patientService.service.IdentityService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/identities")
@RequiredArgsConstructor
public class IdentityController {

	private final IdentityService identityService;

	@GetMapping
	public List<IdentityResponse> getAll() {
		return identityService.findAll();
	}

	@GetMapping("/{id}")
	public IdentityResponse getById(@PathVariable UUID id) {
		return identityService.findById(id);
	}

	@PostMapping
	@ResponseStatus(HttpStatus.CREATED)
	public IdentityResponse create(@Valid @RequestBody IdentityRequest request) {
		return identityService.create(request);
	}

	@PutMapping("/{id}")
	public IdentityResponse update(@PathVariable UUID id, @Valid @RequestBody IdentityRequest request) {
		return identityService.update(id, request);
	}

	@DeleteMapping("/{id}")
	@ResponseStatus(HttpStatus.NO_CONTENT)
	public void delete(@PathVariable UUID id) {
		identityService.delete(id);
	}

}
