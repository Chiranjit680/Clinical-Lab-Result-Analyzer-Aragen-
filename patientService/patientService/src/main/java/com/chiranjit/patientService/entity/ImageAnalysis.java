package com.chiranjit.patientService.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.FetchType;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.OneToOne;
import jakarta.persistence.Table;
import lombok.Getter;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;

import java.time.Instant;
import java.util.Map;
import java.util.UUID;

/**
 * The stored result of running the VLM agents over one radiological image.
 *
 * At most one per image — the unique constraint on image_id means a re-analysis
 * replaces the previous result rather than accumulating, matching how
 * {@link Analysis} behaves for lab reports.
 */
@Entity
@Table(name = "image_analysis")
@Getter
@Setter
public class ImageAnalysis {

	@Id
	@GeneratedValue(strategy = GenerationType.UUID)
	private UUID id;

	@OneToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "image_id", unique = true)
	private RadiologyImage image;

	private String question;

	/** The aggregator's merged answer. Long enough to need TEXT, not VARCHAR. */
	@Column(columnDefinition = "text")
	private String answer;

	private String model;

	/** Correlates this row with the agent service's log of the run. */
	private String runId;

	private int tileCount;

	private Integer durationMs;

	/**
	 * The agents' full response, stored as jsonb so the whole-image summary and
	 * every per-tile report can be re-rendered without this table needing a
	 * migration each time that shape changes.
	 */
	@JdbcTypeCode(SqlTypes.JSON)
	@Column(columnDefinition = "jsonb")
	private Map<String, Object> payload;

	private Instant createdAt;

}
