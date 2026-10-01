package com.chiranjit.patientService.repository;

import com.chiranjit.patientService.entity.LabReport;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface LabReportRepository extends JpaRepository<LabReport, UUID> {

	List<LabReport> findByPatientIdOrderByCreatedAtDesc(UUID patientId);

}
