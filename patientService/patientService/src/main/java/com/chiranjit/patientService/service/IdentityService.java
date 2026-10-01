package com.chiranjit.patientService.service;

import com.chiranjit.patientService.dto.IdentityRequest;
import com.chiranjit.patientService.dto.IdentityResponse;
import com.chiranjit.patientService.entity.Identity;
import com.chiranjit.patientService.repository.IdentityRepository;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.web.server.ResponseStatusException;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

@Service
@RequiredArgsConstructor
public class IdentityService {

	private final IdentityRepository identityRepository;

	public List<IdentityResponse> findAll() {
		return identityRepository.findAll().stream().map(this::toResponse).toList();
	}

	public IdentityResponse findById(UUID id) {
		return toResponse(getOrThrow(id));
	}

	public IdentityResponse create(IdentityRequest request) {
		Instant now = Instant.now();

		Identity identity = new Identity();
		applyRequest(identity, request);
		identity.setCreatedAt(now);
		identity.setUpdatedAt(now);

		return toResponse(identityRepository.save(identity));
	}

	public IdentityResponse update(UUID id, IdentityRequest request) {
		Identity identity = getOrThrow(id);
		applyRequest(identity, request);
		identity.setUpdatedAt(Instant.now());

		return toResponse(identityRepository.save(identity));
	}

	public void delete(UUID id) {
		identityRepository.delete(getOrThrow(id));
	}

	private Identity getOrThrow(UUID id) {
		return identityRepository.findById(id)
				.orElseThrow(() -> new ResponseStatusException(HttpStatus.NOT_FOUND, "Patient not found: " + id));
	}

	private void applyRequest(Identity identity, IdentityRequest request) {
		identity.setFullName(request.fullName());
		identity.setDateOfBirth(request.dateOfBirth());
		identity.setSex(request.sex());
		identity.setBloodGroup(request.bloodGroup());
		identity.setPregnant(Boolean.TRUE.equals(request.pregnant()));
	}

	private IdentityResponse toResponse(Identity identity) {
		return new IdentityResponse(identity.getId(), identity.getFullName(), identity.getDateOfBirth(),
				identity.getSex(), identity.getBloodGroup(), identity.isPregnant(), identity.getCreatedAt(),
				identity.getUpdatedAt());
	}

}
