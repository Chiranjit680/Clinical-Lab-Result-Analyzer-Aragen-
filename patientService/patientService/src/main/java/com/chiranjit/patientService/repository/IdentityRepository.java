package com.chiranjit.patientService.repository;

import com.chiranjit.patientService.entity.Identity;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface IdentityRepository extends JpaRepository<Identity, UUID> {

}
