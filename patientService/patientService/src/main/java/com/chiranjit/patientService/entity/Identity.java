package com.chiranjit.patientService.entity;

import jakarta.annotation.Generated;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.Id;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;

import java.time.Instant;
import java.time.LocalDate;
import java.util.UUID;

@Entity
@Table(name = "patient")
@Getter
@Setter

public class Identity {

	@Id
	@GeneratedValue(
		strategy = jakarta.persistence.GenerationType.UUID
	)
	private UUID id;

	private String fullName;

	private LocalDate dateOfBirth;

	private String sex;

	private String bloodGroup;

	private boolean pregnant;

	private Instant createdAt;

	private Instant updatedAt;

}
