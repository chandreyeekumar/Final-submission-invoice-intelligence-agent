from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import chromadb
from rapidfuzz.fuzz import ratio

from app.core.config import get_settings
from app.core.embeddings import HashEmbeddingFunction
from app.schemas.rag import (
    RAGDecision,
    VendorCandidate,
)


def normalize(value: str | None) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        (value or "").lower(),
    ).strip()


def compact_identifier(
    value: str | None,
) -> str:
    """Remove separators while preserving letters and digits."""

    return re.sub(
        r"[^a-z0-9]+",
        "",
        (value or "").lower(),
    )


def _first_group(
    payload: dict,
    key: str,
) -> list:
    groups = payload.get(key) or [[]]
    return groups[0] if groups else []


class VendorRAG:
    def __init__(
        self,
        client: Any | None = None,
    ) -> None:
        self.settings = get_settings()

        Path(
            self.settings.chroma_path
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        dimensions = int(
            getattr(
                self.settings,
                "rag_embedding_dimensions",
                384,
            )
        )

        self.embedding_function = (
            HashEmbeddingFunction(
                dimensions=dimensions
            )
        )

        self.client = (
            client
            or chromadb.PersistentClient(
                path=self.settings.chroma_path
            )
        )

        kwargs = {
            "embedding_function":
                self.embedding_function
        }

        try:
            self.vendor = (
                self.client.get_collection(
                    name=(
                        self.settings
                        .chroma_vendor_collection
                    ),
                    **kwargs,
                )
            )

            self.templates = (
                self.client.get_collection(
                    name=(
                        self.settings
                        .chroma_template_collection
                    ),
                    **kwargs,
                )
            )

            self.history = (
                self.client.get_collection(
                    name=(
                        self.settings
                        .chroma_history_collection
                    ),
                    **kwargs,
                )
            )

        except Exception as exc:
            raise RuntimeError(
                "Chroma collections are not ready. "
                "Run: python "
                "scripts/generate_vendor_templates.py, "
                "then python scripts/seed_chroma.py"
            ) from exc

    def _support(
        self,
        collection: Any,
        query: str,
        vendor_id: str,
        min_score: float,
    ) -> list[dict]:
        count = int(
            collection.count()
        )

        if count == 0:
            return []

        result = collection.query(
            query_texts=[query],
            n_results=min(3, count),
            where={
                "vendor_id": vendor_id
            },
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        evidence: list[dict] = []

        for document, metadata, distance in zip(
            _first_group(
                result,
                "documents",
            ),
            _first_group(
                result,
                "metadatas",
            ),
            _first_group(
                result,
                "distances",
            ),
        ):
            cosine_distance = float(
                distance
            )

            score = max(
                0.0,
                min(
                    1.0,
                    1.0 - cosine_distance,
                ),
            )

            if score < float(min_score):
                continue

            evidence.append(
                {
                    "document": document,
                    "metadata": metadata,
                    "distance": (
                        cosine_distance
                    ),
                    "score": round(
                        score,
                        4,
                    ),
                }
            )

        return evidence

    @staticmethod
    def _name_similarity(
        invoice_name: str,
        metadata: dict,
    ) -> float:
        names = [
            str(
                metadata.get(
                    "legal_name",
                    "",
                )
            )
        ]

        try:
            aliases = json.loads(
                str(
                    metadata.get(
                        "aliases_json",
                        "[]",
                    )
                )
            )

            if isinstance(aliases, list):
                names.extend(
                    str(alias)
                    for alias in aliases
                )

        except (
            TypeError,
            json.JSONDecodeError,
        ):
            pass

        normalized_invoice_name = normalize(
            invoice_name
        )

        return max(
            (
                ratio(
                    normalized_invoice_name,
                    normalize(name),
                )
                for name in names
                if normalize(name)
            ),
            default=0.0,
        )

    def query(
        self,
        invoice,
    ) -> RAGDecision:
        if not getattr(
            invoice,
            "vendor_name",
            None,
        ):
            return RAGDecision(
                status="not_applicable",
                issues=[
                    "vendor_name_missing"
                ],
                recommended_action=(
                    "human_review"
                ),
            )

        vendor_count = int(
            self.vendor.count()
        )

        if vendor_count == 0:
            return RAGDecision(
                status="unknown",
                issues=[
                    "vendor_collection_empty"
                ],
                recommended_action=(
                    "human_review"
                ),
            )

        query_text = (
            f"Vendor "
            f"{invoice.vendor_name}. "
            f"Address "
            f"{getattr(invoice, 'vendor_address', None) or ''}. "
            f"Tax ID "
            f"{getattr(invoice, 'vendor_tax_id', None) or ''}. "
            f"Currency "
            f"{getattr(invoice, 'currency', None) or ''}. "
            f"Invoice "
            f"{getattr(invoice, 'invoice_number', None) or ''}."
        )

        result = self.vendor.query(
            query_texts=[query_text],
            n_results=min(
                int(
                    self.settings.rag_top_k
                ),
                vendor_count,
            ),
            where={
                "active": True
            },
            include=[
                "documents",
                "metadatas",
                "distances",
            ],
        )

        candidates = [
            VendorCandidate(
                vendor_id=str(
                    metadata["vendor_id"]
                ),
                legal_name=str(
                    metadata["legal_name"]
                ),
                distance=float(
                    distance
                ),
                metadata=metadata,
            )
            for metadata, distance in zip(
                _first_group(
                    result,
                    "metadatas",
                ),
                _first_group(
                    result,
                    "distances",
                ),
            )
        ]

        if (
            not candidates
            or candidates[0].distance
            > float(
                self.settings.rag_max_distance
            )
        ):
            return RAGDecision(
                status="unknown",
                candidates=candidates,
                issues=[
                    "no_reliable_vendor_match"
                ],
                recommended_action=(
                    "human_review"
                ),
            )

        best = candidates[0]
        metadata = best.metadata

        name_similarity = (
            self._name_similarity(
                invoice.vendor_name,
                metadata,
            )
        )

        invoice_tax_id = getattr(
            invoice,
            "vendor_tax_id",
            None,
        )

        invoice_currency = getattr(
            invoice,
            "currency",
            None,
        )

        invoice_bank = getattr(
            invoice,
            "vendor_bank_account",
            None,
        )

        stored_bank_last4 = (
            compact_identifier(
                str(
                    metadata.get(
                        "bank_last4",
                        "",
                    )
                )
            )[-4:]
        )

        invoice_bank_last4 = (
            compact_identifier(
                invoice_bank
            )[-4:]
        )

        checks = {
            "name_similarity_ok": (
                name_similarity >= 70
            ),
            "tax_id_match": (
                None
                if not invoice_tax_id
                else compact_identifier(
                    invoice_tax_id
                )
                == compact_identifier(
                    str(
                        metadata.get(
                            "tax_id",
                            "",
                        )
                    )
                )
            ),
            "currency_match": (
                None
                if not invoice_currency
                else str(
                    invoice_currency
                ).strip().upper()
                == str(
                    metadata.get(
                        "currency",
                        "",
                    )
                ).strip().upper()
            ),
            "bank_last4_match": (
                None
                if not invoice_bank
                else bool(
                    stored_bank_last4
                )
                and (
                    invoice_bank_last4
                    == stored_bank_last4
                )
            ),
        }

        issues = [
            name
            for name, passed
            in checks.items()
            if passed is False
        ]

        template_evidence = (
            self._support(
                self.templates,
                query_text,
                best.vendor_id,
                self.settings
                .rag_min_template_score,
            )
        )

        history_evidence = (
            self._support(
                self.history,
                query_text,
                best.vendor_id,
                self.settings
                .rag_min_history_score,
            )
        )

        hard_mismatches = {
            "tax_id_match",
            "currency_match",
            "bank_last4_match",
        }

        if hard_mismatches.intersection(
            issues
        ):
            return RAGDecision(
                status="mismatch",
                matched_vendor_id=(
                    best.vendor_id
                ),
                matched_legal_name=(
                    best.legal_name
                ),
                candidates=candidates,
                exact_checks=checks,
                template_evidence=(
                    template_evidence
                ),
                history_evidence=(
                    history_evidence
                ),
                issues=issues,
                recommended_action=(
                    "human_review"
                ),
            )

        if (
            len(candidates) > 1
            and abs(
                candidates[1].distance
                - best.distance
            )
            < float(
                self.settings
                .rag_ambiguity_margin
            )
        ):
            return RAGDecision(
                status="ambiguous",
                matched_vendor_id=(
                    best.vendor_id
                ),
                matched_legal_name=(
                    best.legal_name
                ),
                candidates=candidates,
                exact_checks=checks,
                template_evidence=(
                    template_evidence
                ),
                history_evidence=(
                    history_evidence
                ),
                issues=[
                    "close_competing_candidates",
                    *issues,
                ],
                recommended_action=(
                    "human_review"
                ),
            )

        if (
            checks["name_similarity_ok"]
            is False
        ):
            return RAGDecision(
                status="mismatch",
                matched_vendor_id=(
                    best.vendor_id
                ),
                matched_legal_name=(
                    best.legal_name
                ),
                candidates=candidates,
                exact_checks=checks,
                template_evidence=(
                    template_evidence
                ),
                history_evidence=(
                    history_evidence
                ),
                issues=issues,
                recommended_action=(
                    "human_review"
                ),
            )

        return RAGDecision(
            status="verified",
            matched_vendor_id=(
                best.vendor_id
            ),
            matched_legal_name=(
                best.legal_name
            ),
            candidates=candidates,
            exact_checks=checks,
            template_evidence=(
                template_evidence
            ),
            history_evidence=(
                history_evidence
            ),
            issues=issues,
            recommended_action=(
                "correct_name"
                if normalize(
                    invoice.vendor_name
                )
                != normalize(
                    best.legal_name
                )
                else "continue"
            ),
        )