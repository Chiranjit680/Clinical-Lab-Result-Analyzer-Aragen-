package com.chiranjit.patientService.entity;

import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.util.UUID;

/** One stored radiological image belonging to a patient. */
@Entity
@Table(name = "radiology_image")
@Getter
@Setter
public class RadiologyImage {

	@Id
	@GeneratedValue(strategy = GenerationType.UUID)
	private UUID id;

	@ManyToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "patient_id")
	private Identity patient;

	private String imagePath;

	@Enumerated(EnumType.STRING)
	private Modality modality;

	private String bodyPart;

	private String description;

	private Instant createdAt;

}
