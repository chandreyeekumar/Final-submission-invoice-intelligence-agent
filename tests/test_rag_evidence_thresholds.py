from typing import Any

from app.agents.rag import VendorRAG


class FakeCollection:
    def count(self) -> int:
        return 2

    def query(self, **kwargs: Any) -> dict:
        return {
            "documents": [
                [
                    "weak evidence",
                    "strong evidence",
                ]
            ],
            "metadatas": [
                [
                    {
                        "vendor_id": "V1",
                    },
                    {
                        "vendor_id": "V1",
                    },
                ]
            ],
            "distances": [
                [
                    0.80,
                    0.20,
                ]
            ],
        }


def test_support_filters_evidence_below_quality_threshold() -> None:
    rag_agent = VendorRAG.__new__(VendorRAG)
    collection = FakeCollection()

    evidence = rag_agent._support(
        collection=collection,
        query="Acme invoice",
        vendor_id="V1",
        min_score=0.45,
    )

    assert len(evidence) == 1
    assert evidence[0]["document"] == "strong evidence"
    assert evidence[0]["score"] == 0.8
    assert evidence[0]["distance"] == 0.2