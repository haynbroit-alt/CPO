"""Seed data — 12 anonymized audit records for the Proof Gallery."""

from __future__ import annotations

from datetime import datetime, timezone

from sios.proof_layer.models import (
    AnomalyType,
    AuditAnomaly,
    AuditArtifact,
    AuditRecord,
    DetectionLayer,
    RawDataLayer,
    VerificationLayer,
    VerificationLevel,
)

_DT = lambda y, m, d: datetime(y, m, d, tzinfo=timezone.utc)  # noqa: E731


def _timeline(ingest_date: datetime, detect_date: datetime, validate_date: datetime, recover_date: datetime) -> list:
    return [
        {"step": 1, "label": "Data ingestion", "date": ingest_date.isoformat(), "detail": "Transactions loaded, dataset hashed, immutable snapshot created"},
        {"step": 2, "label": "SIOS detection", "date": detect_date.isoformat(), "detail": "All detectors applied, anomalies scored and ranked"},
        {"step": 3, "label": "Human validation", "date": validate_date.isoformat(), "detail": "Client reviewed findings, confirmed or dismissed each anomaly"},
        {"step": 4, "label": "Recovery confirmed", "date": recover_date.isoformat(), "detail": "Corrective action taken, savings recorded"},
    ]


def _artifacts(ds_hash: str, det_hash: str, model: str) -> list:
    return [
        AuditArtifact(label="Dataset hash (SHA-256)", artifact_type="hash", value=ds_hash, generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        AuditArtifact(label="Detection output hash", artifact_type="hash", value=det_hash, generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        AuditArtifact(label="Model version", artifact_type="log", value=model, generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc)),
        AuditArtifact(label="Detection rules applied", artifact_type="query", value="duplicate_payment_v2, unused_subscription_v3, cloud_waste_v1, cost_anomaly_v2", generated_at=datetime(2025, 1, 1, tzinfo=timezone.utc)),
    ]


SEED_AUDITS: list[AuditRecord] = [

    # ── 0042 — SaaS — CLIENT VERIFIED ────────────────────────────────────────
    AuditRecord(
        id="audit-0042",
        audit_number=42,
        sector="SaaS",
        audit_date=_DT(2025, 3, 15),
        transactions_analyzed=12483,
        anomalies_detected=3,
        estimated_savings_eur=4700.0,
        confirmed_savings_eur=4500.0,
        confidence_pct=97,
        anomalies=[
            AuditAnomaly(type=AnomalyType.UNUSED_LICENSE, vendor="Slack", description="2 licences inactives depuis 4 mois", estimated_amount=960.0, confirmed_amount=960.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_LICENSE, vendor="Salesforce", description="3 sièges jamais utilisés", estimated_amount=2340.0, confirmed_amount=2340.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="AWS", description="Doublon de facturation détecté", estimated_amount=1400.0, confirmed_amount=1200.0, trust_tier="HIGH"),
        ],
        raw_data=RawDataLayer(dataset_hash="a1b2c3d4e5f6789012345678901234567890abcd", transaction_count=12483, ingested_at=_DT(2025, 3, 15), source="stripe", period_months=12),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["unused_license_v2", "duplicate_payment_v2"], anomalies_found=3, detection_hash="9f3a1d2e4b5c6a7f8e9d0c1b2a3f4e5d6c7b8a9f", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.CLIENT_VERIFIED, client_approved=True, accountant_validated=True, approved_at=_DT(2025, 3, 22), approver_role="CFO", signature_ref="sig-cfo-2025-03-22"),
        timeline=_timeline(_DT(2025, 3, 15), _DT(2025, 3, 15), _DT(2025, 3, 22), _DT(2025, 3, 28)),
        artifacts=_artifacts("a1b2c3d4e5f6789012345678901234567890abcd", "9f3a1d2e4b5c6a7f8e9d0c1b2a3f4e5d6c7b8a9f", "sios-v3.2"),
    ),

    # ── 0063 — Finance — CLIENT VERIFIED ─────────────────────────────────────
    AuditRecord(
        id="audit-0063",
        audit_number=63,
        sector="Finance",
        audit_date=_DT(2025, 2, 8),
        transactions_analyzed=34210,
        anomalies_detected=5,
        estimated_savings_eur=18400.0,
        confirmed_savings_eur=17200.0,
        confidence_pct=95,
        anomalies=[
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Bloomberg Terminal", description="Double facturation mensuelle", estimated_amount=6400.0, confirmed_amount=6400.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="Refinitiv", description="Abonnement data non utilisé, 8 mois", estimated_amount=7200.0, confirmed_amount=6800.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="Azure", description="Environnements dev/test actifs 24/7", estimated_amount=2800.0, confirmed_amount=2800.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.TELECOM_OVERCHARGE, vendor="Orange Business", description="Lignes mobiles inutilisées", estimated_amount=1200.0, confirmed_amount=1200.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="DocuSign", description="Pic de facturation inexpliqué (×3)", estimated_amount=800.0, trust_tier="MEDIUM"),
        ],
        raw_data=RawDataLayer(dataset_hash="b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1", transaction_count=34210, ingested_at=_DT(2025, 2, 8), source="erp", period_months=12),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["duplicate_payment_v2", "unused_subscription_v3", "cloud_waste_v1", "telecom_v1", "cost_anomaly_v2"], anomalies_found=5, detection_hash="1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.CLIENT_VERIFIED, client_approved=True, accountant_validated=True, approved_at=_DT(2025, 2, 15), approver_role="Finance Director", signature_ref="sig-fd-2025-02-15"),
        timeline=_timeline(_DT(2025, 2, 8), _DT(2025, 2, 8), _DT(2025, 2, 15), _DT(2025, 2, 20)),
        artifacts=_artifacts("b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1", "1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b", "sios-v3.2"),
    ),

    # ── 0078 — Retail — CLIENT VERIFIED ──────────────────────────────────────
    AuditRecord(
        id="audit-0078",
        audit_number=78,
        sector="Retail",
        audit_date=_DT(2025, 1, 20),
        transactions_analyzed=8920,
        anomalies_detected=4,
        estimated_savings_eur=9300.0,
        confirmed_savings_eur=9100.0,
        confidence_pct=96,
        anomalies=[
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="Salesforce Commerce", description="Modules CMS non activés, 6 mois", estimated_amount=4800.0, confirmed_amount=4800.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Shopify Plus", description="Frais plateforme facturés deux fois", estimated_amount=2100.0, confirmed_amount=2100.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="GCP", description="Clusters Kubernetes sous-utilisés", estimated_amount=1800.0, confirmed_amount=1800.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="Twilio", description="Surcoût SMS campagnes nocturnes", estimated_amount=600.0, confirmed_amount=400.0, trust_tier="MEDIUM"),
        ],
        raw_data=RawDataLayer(dataset_hash="c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2", transaction_count=8920, ingested_at=_DT(2025, 1, 20), source="csv", period_months=6),
        detection=DetectionLayer(model_version="sios-v3.1", rules_applied=["unused_subscription_v3", "duplicate_payment_v2", "cloud_waste_v1", "cost_anomaly_v2"], anomalies_found=4, detection_hash="2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.CLIENT_VERIFIED, client_approved=True, accountant_validated=False, approved_at=_DT(2025, 1, 28), approver_role="CFO"),
        timeline=_timeline(_DT(2025, 1, 20), _DT(2025, 1, 20), _DT(2025, 1, 28), _DT(2025, 2, 3)),
        artifacts=_artifacts("c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2", "2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c", "sios-v3.1"),
    ),

    # ── 0091 — Manufacturing — INTERNAL VERIFIED ─────────────────────────────
    AuditRecord(
        id="audit-0091",
        audit_number=91,
        sector="Manufacturing",
        audit_date=_DT(2025, 4, 5),
        transactions_analyzed=21340,
        anomalies_detected=6,
        estimated_savings_eur=32000.0,
        confirmed_savings_eur=28500.0,
        confidence_pct=93,
        anomalies=[
            AuditAnomaly(type=AnomalyType.RENEGOTIABLE_CONTRACT, vendor="SAP Maintenance", description="Contrat maintenance au tarif catalogue +40%", estimated_amount=18000.0, confirmed_amount=16000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_LICENSE, vendor="AutoCAD", description="15 licences dormantes depuis migration", estimated_amount=7200.0, confirmed_amount=7200.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.TELECOM_OVERCHARGE, vendor="SFR Business", description="Options data non souscrites facturées", estimated_amount=3600.0, confirmed_amount=3600.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="AWS", description="Snapshots EBS orphelins non supprimés", estimated_amount=1800.0, confirmed_amount=1700.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Oracle", description="Double facturation trimestrielle", estimated_amount=900.0, confirmed_amount=0.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="Microsoft 365", description="Augmentation tarifaire non contractuelle", estimated_amount=500.0, trust_tier="LOW"),
        ],
        raw_data=RawDataLayer(dataset_hash="d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3", transaction_count=21340, ingested_at=_DT(2025, 4, 5), source="erp", period_months=18),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["renegotiable_v1", "unused_license_v2", "telecom_v1", "cloud_waste_v1", "duplicate_payment_v2", "cost_anomaly_v2"], anomalies_found=6, detection_hash="3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d", reproducible=True, drift_pct=0.1),
        verification=VerificationLayer(level=VerificationLevel.INTERNAL_ONLY, client_approved=False, accountant_validated=True, approved_at=_DT(2025, 4, 12), approver_role="Controller"),
        timeline=_timeline(_DT(2025, 4, 5), _DT(2025, 4, 5), _DT(2025, 4, 12), _DT(2025, 4, 25)),
        artifacts=_artifacts("d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3", "3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d", "sios-v3.2"),
    ),

    # ── 0105 — Healthcare — REPRODUCIBLE ONLY ────────────────────────────────
    AuditRecord(
        id="audit-0105",
        audit_number=105,
        sector="Healthcare",
        audit_date=_DT(2025, 5, 12),
        transactions_analyzed=6780,
        anomalies_detected=2,
        estimated_savings_eur=5200.0,
        confidence_pct=88,
        anomalies=[
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="Epic Systems", description="Modules analytics non déployés", estimated_amount=3600.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="AWS", description="Instances de test non éteintes", estimated_amount=1600.0, trust_tier="MEDIUM"),
        ],
        raw_data=RawDataLayer(dataset_hash="e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4", transaction_count=6780, ingested_at=_DT(2025, 5, 12), source="csv", period_months=6),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["unused_subscription_v3", "cloud_waste_v1"], anomalies_found=2, detection_hash="4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.REPRODUCIBLE_ONLY, client_approved=False, accountant_validated=False),
        timeline=_timeline(_DT(2025, 5, 12), _DT(2025, 5, 12), _DT(2025, 5, 12), _DT(2025, 5, 12)),
        artifacts=_artifacts("e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4", "4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e", "sios-v3.2"),
    ),

    # ── 0117 — Logistics — CLIENT VERIFIED ───────────────────────────────────
    AuditRecord(
        id="audit-0117",
        audit_number=117,
        sector="Logistics",
        audit_date=_DT(2025, 3, 28),
        transactions_analyzed=45600,
        anomalies_detected=7,
        estimated_savings_eur=67000.0,
        confirmed_savings_eur=61000.0,
        confidence_pct=94,
        anomalies=[
            AuditAnomaly(type=AnomalyType.RENEGOTIABLE_CONTRACT, vendor="Geodis", description="Contrat transport aérien hors marché", estimated_amount=35000.0, confirmed_amount=31000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Chronopost", description="Doublons sur 6 commandes de groupe", estimated_amount=12000.0, confirmed_amount=12000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="Transporeon", description="Licences TMS non utilisées", estimated_amount=8400.0, confirmed_amount=8400.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="Azure", description="VM fleet surdimensionnée", estimated_amount=4800.0, confirmed_amount=4800.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.TELECOM_OVERCHARGE, vendor="Bouygues Telecom", description="Flotte mobile facturée sur anciens tarifs", estimated_amount=3600.0, confirmed_amount=3600.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="Fuel cards", description="Pic hors-norme Q4 vs baseline", estimated_amount=2200.0, confirmed_amount=1200.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.UNUSED_LICENSE, vendor="WMS Pro", description="3 licences entrepôt fermé", estimated_amount=1000.0, confirmed_amount=0.0, trust_tier="LOW"),
        ],
        raw_data=RawDataLayer(dataset_hash="f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5", transaction_count=45600, ingested_at=_DT(2025, 3, 28), source="erp", period_months=24),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["renegotiable_v1", "duplicate_payment_v2", "unused_subscription_v3", "cloud_waste_v1", "telecom_v1", "cost_anomaly_v2", "unused_license_v2"], anomalies_found=7, detection_hash="5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.CLIENT_VERIFIED, client_approved=True, accountant_validated=True, approved_at=_DT(2025, 4, 8), approver_role="CFO", signature_ref="sig-cfo-2025-04-08"),
        timeline=_timeline(_DT(2025, 3, 28), _DT(2025, 3, 28), _DT(2025, 4, 8), _DT(2025, 4, 15)),
        artifacts=_artifacts("f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5", "5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f", "sios-v3.2"),
    ),

    # ── 0133 — SaaS — INTERNAL VERIFIED ──────────────────────────────────────
    AuditRecord(
        id="audit-0133",
        audit_number=133,
        sector="SaaS",
        audit_date=_DT(2025, 4, 22),
        transactions_analyzed=5340,
        anomalies_detected=4,
        estimated_savings_eur=11200.0,
        confirmed_savings_eur=10400.0,
        confidence_pct=91,
        anomalies=[
            AuditAnomaly(type=AnomalyType.UNUSED_LICENSE, vendor="GitHub Enterprise", description="Sièges dormants après réorg", estimated_amount=4800.0, confirmed_amount=4800.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="Datadog", description="APM tier non utilisé en prod", estimated_amount=3600.0, confirmed_amount=3200.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="AWS", description="Lambda invocations idle — 3 régions", estimated_amount=1800.0, confirmed_amount=1800.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="Stripe fees", description="Frais interchange anormaux Q1", estimated_amount=1000.0, confirmed_amount=600.0, trust_tier="MEDIUM"),
        ],
        raw_data=RawDataLayer(dataset_hash="a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6", transaction_count=5340, ingested_at=_DT(2025, 4, 22), source="stripe", period_months=9),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["unused_license_v2", "unused_subscription_v3", "cloud_waste_v1", "cost_anomaly_v2"], anomalies_found=4, detection_hash="6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.INTERNAL_ONLY, client_approved=False, accountant_validated=True, approved_at=_DT(2025, 4, 28), approver_role="Controller"),
        timeline=_timeline(_DT(2025, 4, 22), _DT(2025, 4, 22), _DT(2025, 4, 28), _DT(2025, 5, 5)),
        artifacts=_artifacts("a7b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6", "6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a", "sios-v3.2"),
    ),

    # ── 0148 — Media — CLIENT VERIFIED ───────────────────────────────────────
    AuditRecord(
        id="audit-0148",
        audit_number=148,
        sector="Media",
        audit_date=_DT(2025, 5, 3),
        transactions_analyzed=9870,
        anomalies_detected=3,
        estimated_savings_eur=14500.0,
        confirmed_savings_eur=14200.0,
        confidence_pct=98,
        anomalies=[
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Getty Images", description="Factures agency dupliquées 3 mois", estimated_amount=9600.0, confirmed_amount=9600.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="Adobe Creative Cloud", description="30 licences équipes parties", estimated_amount=3600.0, confirmed_amount=3600.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="Akamai CDN", description="Surprovisionnement bande passante", estimated_amount=1300.0, confirmed_amount=1000.0, trust_tier="MEDIUM"),
        ],
        raw_data=RawDataLayer(dataset_hash="b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7", transaction_count=9870, ingested_at=_DT(2025, 5, 3), source="csv", period_months=12),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["duplicate_payment_v2", "unused_subscription_v3", "cloud_waste_v1"], anomalies_found=3, detection_hash="7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.CLIENT_VERIFIED, client_approved=True, accountant_validated=True, approved_at=_DT(2025, 5, 10), approver_role="CFO", signature_ref="sig-cfo-2025-05-10"),
        timeline=_timeline(_DT(2025, 5, 3), _DT(2025, 5, 3), _DT(2025, 5, 10), _DT(2025, 5, 17)),
        artifacts=_artifacts("b8c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7", "7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b", "sios-v3.2"),
    ),

    # ── 0162 — Finance — INTERNAL VERIFIED ───────────────────────────────────
    AuditRecord(
        id="audit-0162",
        audit_number=162,
        sector="Finance",
        audit_date=_DT(2025, 5, 20),
        transactions_analyzed=78300,
        anomalies_detected=8,
        estimated_savings_eur=142000.0,
        confirmed_savings_eur=128000.0,
        confidence_pct=92,
        anomalies=[
            AuditAnomaly(type=AnomalyType.RENEGOTIABLE_CONTRACT, vendor="FIS", description="Contrat processing paiements hors marché", estimated_amount=86000.0, confirmed_amount=76000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_LICENSE, vendor="Murex", description="Modules derivatives inactifs", estimated_amount=28000.0, confirmed_amount=28000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Reuters", description="4 doublons data feed sur 6 mois", estimated_amount=14400.0, confirmed_amount=14400.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="Azure", description="Disaster recovery surdimensionné", estimated_amount=6400.0, confirmed_amount=6400.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.TELECOM_OVERCHARGE, vendor="AT&T", description="Lignes dédiées inutilisées post-fusion", estimated_amount=4800.0, confirmed_amount=3200.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="Moody's Analytics", description="Abonnement facturé au tarif retail", estimated_amount=1600.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="FactSet", description="Terminal non attribué", estimated_amount=600.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="Refinitiv", description="Surcoût API calls Q1", estimated_amount=200.0, trust_tier="LOW"),
        ],
        raw_data=RawDataLayer(dataset_hash="c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8", transaction_count=78300, ingested_at=_DT(2025, 5, 20), source="erp", period_months=24),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["renegotiable_v1", "unused_license_v2", "duplicate_payment_v2", "cloud_waste_v1", "telecom_v1", "cost_anomaly_v2", "unused_subscription_v3"], anomalies_found=8, detection_hash="8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c", reproducible=True, drift_pct=0.2),
        verification=VerificationLayer(level=VerificationLevel.INTERNAL_ONLY, client_approved=False, accountant_validated=True, approved_at=_DT(2025, 5, 27), approver_role="Head of Finance"),
        timeline=_timeline(_DT(2025, 5, 20), _DT(2025, 5, 20), _DT(2025, 5, 27), _DT(2025, 6, 10)),
        artifacts=_artifacts("c9d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8", "8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c", "sios-v3.2"),
    ),

    # ── 0174 — SaaS — CLIENT VERIFIED ────────────────────────────────────────
    AuditRecord(
        id="audit-0174",
        audit_number=174,
        sector="SaaS",
        audit_date=_DT(2025, 6, 2),
        transactions_analyzed=3120,
        anomalies_detected=2,
        estimated_savings_eur=3800.0,
        confirmed_savings_eur=3800.0,
        confidence_pct=99,
        anomalies=[
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Intercom", description="Doublon migration plan annuel→mensuel", estimated_amount=2400.0, confirmed_amount=2400.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.UNUSED_LICENSE, vendor="Figma", description="5 licences design équipe réduite", estimated_amount=1400.0, confirmed_amount=1400.0, trust_tier="HIGH"),
        ],
        raw_data=RawDataLayer(dataset_hash="d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9", transaction_count=3120, ingested_at=_DT(2025, 6, 2), source="stripe", period_months=6),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["duplicate_payment_v2", "unused_license_v2"], anomalies_found=2, detection_hash="9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.CLIENT_VERIFIED, client_approved=True, accountant_validated=False, approved_at=_DT(2025, 6, 5), approver_role="CEO"),
        timeline=_timeline(_DT(2025, 6, 2), _DT(2025, 6, 2), _DT(2025, 6, 5), _DT(2025, 6, 9)),
        artifacts=_artifacts("d0e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9", "9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d", "sios-v3.2"),
    ),

    # ── 0188 — Retail — REPRODUCIBLE ONLY ────────────────────────────────────
    AuditRecord(
        id="audit-0188",
        audit_number=188,
        sector="Retail",
        audit_date=_DT(2025, 6, 10),
        transactions_analyzed=17430,
        anomalies_detected=5,
        estimated_savings_eur=22400.0,
        confidence_pct=89,
        anomalies=[
            AuditAnomaly(type=AnomalyType.UNUSED_SUBSCRIPTION, vendor="Salesforce", description="Licences agents inactifs post-COVID", estimated_amount=9600.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.RENEGOTIABLE_CONTRACT, vendor="Logitech B2B", description="Renouvellement équipement hors marché", estimated_amount=6000.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="AWS", description="RDS multi-AZ sur env. staging", estimated_amount=3600.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.COST_ANOMALY, vendor="PayPal Fees", description="Surcoût frais cross-border Q2", estimated_amount=2000.0, trust_tier="MEDIUM"),
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Zendesk", description="Doublon facturation siège Paris/Lyon", estimated_amount=1200.0, trust_tier="HIGH"),
        ],
        raw_data=RawDataLayer(dataset_hash="e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0", transaction_count=17430, ingested_at=_DT(2025, 6, 10), source="csv", period_months=12),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["unused_subscription_v3", "renegotiable_v1", "cloud_waste_v1", "cost_anomaly_v2", "duplicate_payment_v2"], anomalies_found=5, detection_hash="0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.REPRODUCIBLE_ONLY, client_approved=False, accountant_validated=False),
        timeline=_timeline(_DT(2025, 6, 10), _DT(2025, 6, 10), _DT(2025, 6, 10), _DT(2025, 6, 10)),
        artifacts=_artifacts("e1f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0", "0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e", "sios-v3.2"),
    ),

    # ── 0201 — Manufacturing — CLIENT VERIFIED ────────────────────────────────
    AuditRecord(
        id="audit-0201",
        audit_number=201,
        sector="Manufacturing",
        audit_date=_DT(2025, 6, 18),
        transactions_analyzed=29800,
        anomalies_detected=4,
        estimated_savings_eur=48000.0,
        confirmed_savings_eur=45000.0,
        confidence_pct=96,
        anomalies=[
            AuditAnomaly(type=AnomalyType.RENEGOTIABLE_CONTRACT, vendor="Siemens PLM", description="Licence Teamcenter au-dessus du tarif Enterprise", estimated_amount=28000.0, confirmed_amount=26000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.TELECOM_OVERCHARGE, vendor="Colt Technology", description="Bande passante MPLS non réduite post-consolidation", estimated_amount=12000.0, confirmed_amount=12000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.DUPLICATE_PAYMENT, vendor="Bosch Rexroth", description="3 commandes pièces facturées deux fois", estimated_amount=6000.0, confirmed_amount=6000.0, trust_tier="HIGH"),
            AuditAnomaly(type=AnomalyType.CLOUD_WASTE, vendor="Azure IoT Hub", description="Unités messages inutilisées", estimated_amount=2000.0, confirmed_amount=1000.0, trust_tier="MEDIUM"),
        ],
        raw_data=RawDataLayer(dataset_hash="f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1", transaction_count=29800, ingested_at=_DT(2025, 6, 18), source="erp", period_months=18),
        detection=DetectionLayer(model_version="sios-v3.2", rules_applied=["renegotiable_v1", "telecom_v1", "duplicate_payment_v2", "cloud_waste_v1"], anomalies_found=4, detection_hash="1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f", reproducible=True, drift_pct=0.0),
        verification=VerificationLayer(level=VerificationLevel.CLIENT_VERIFIED, client_approved=True, accountant_validated=True, approved_at=_DT(2025, 6, 25), approver_role="CFO", signature_ref="sig-cfo-2025-06-25"),
        timeline=_timeline(_DT(2025, 6, 18), _DT(2025, 6, 18), _DT(2025, 6, 25), _DT(2025, 6, 28)),
        artifacts=_artifacts("f2a3b4c5d6e7f8a9b0c1d2e3f4a5b6c7d8e9f0a1", "1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f", "sios-v3.2"),
    ),
]


def get_seed_audits() -> list[AuditRecord]:
    return SEED_AUDITS


def gallery_stats() -> dict:
    """Aggregate stats for the hero section."""
    total = len(SEED_AUDITS)
    confirmed = sum(a.confirmed_savings_eur or 0.0 for a in SEED_AUDITS)
    estimated = sum(a.estimated_savings_eur for a in SEED_AUDITS)
    anomaly_count = sum(a.anomalies_detected for a in SEED_AUDITS)
    txn_count = sum(a.transactions_analyzed for a in SEED_AUDITS)
    return {
        "total_audits": total,
        "total_transactions": txn_count,
        "total_anomalies": anomaly_count,
        "total_confirmed_eur": round(confirmed),
        "total_estimated_eur": round(estimated),
        "anomaly_rate_pct": round(anomaly_count / txn_count * 100, 1) if txn_count else 0,
    }
