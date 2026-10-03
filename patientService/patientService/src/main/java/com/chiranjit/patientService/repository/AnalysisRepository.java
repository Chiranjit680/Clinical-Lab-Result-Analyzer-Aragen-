package com.chiranjit.patientService.repository;

import com.chiranjit.patientService.entity.Analysis;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface AnalysisRepository extends JpaRepository<Analysis, UUID> {

	Optional<Analysis> findByReportId(UUID reportId);

	/**
	 * Batch lookup for report listings. Fetching one analysis per report would
	 * be an N+1 query against a list that is already paged by patient.
	 */
	List<Analysis> findByReportIdIn(Collection<UUID> reportIds);

}
