package com.chiranjit.patientService.repository;

import com.chiranjit.patientService.entity.RadiologyImage;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.UUID;

public interface RadiologyImageRepository extends JpaRepository<RadiologyImage, UUID> {

	List<RadiologyImage> findByPatientIdOrderByCreatedAtDesc(UUID patientId);

}
