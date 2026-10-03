package com.chiranjit.patientService.repository;

import com.chiranjit.patientService.entity.ImageAnalysis;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ImageAnalysisRepository extends JpaRepository<ImageAnalysis, UUID> {

	Optional<ImageAnalysis> findByImageId(UUID imageId);

	/**
	 * Batch lookup for image listings. Fetching one analysis per image would be
	 * an N+1 query against a list that is already paged by patient.
	 */
	List<ImageAnalysis> findByImageIdIn(Collection<UUID> imageIds);

}
