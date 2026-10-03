package com.chiranjit.patientService.entity;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
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
 * The stored result of analysing one report.
 *
 * At most one per report — the unique constraint on report_id means a
 * re-analysis replaces the previous result rather than accumulating.
 */
@Entity
@Table(name = "analysis")
@Getter
@Setter
public class Analysis {

	@Id
	@GeneratedValue(strategy = GenerationType.UUID)
	private UUID id;

	@OneToOne(fetch = FetchType.LAZY, optional = false)
	@JoinColumn(name = "report_id", unique = true)
	private LabReport report;

	private String threadId;

	@Enumerated(EnumType.STRING)
	private ReportStatus status;

	private int criticalCount;

	private int warningCount;

	private int normalCount;

	private int unknownCount;

	private int errorCount;

	private Integer durationMs;

	/**
	 * The analyzer's full response, stored as jsonb so the UI can re-render a
	 * past analysis — explanations, sources and next steps included — without
	 * this table needing a migration each time that shape changes.
	 */
	@JdbcTypeCode(SqlTypes.JSON)
	@Column(columnDefinition = "jsonb")
	private Map<String, Object> payload;

	private Instant createdAt;

}
