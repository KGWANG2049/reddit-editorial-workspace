from __future__ import annotations


def test_process_documents_creates_independent_jobs(client):
    response = client.post(
        "/documents/process",
        json={
            "urls": [
                "https://example.com/one",
                "https://example.com/two",
                "https://example.com/one",
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["accepted"] == 2
    assert len(payload["items"]) == 2
    assert payload["items"][0]["document"]["source_url"] == "https://example.com/one"
    assert payload["items"][1]["document"]["source_url"] == "https://example.com/two"


def test_get_document_detail_returns_job_slot(client):
    queue_response = client.post(
        "/documents/process",
        json={"urls": ["https://example.com/article"]},
    )
    document_id = queue_response.json()["items"][0]["document"]["id"]

    response = client.get(f"/documents/{document_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == document_id
    assert payload["latest_job"]["target_id"] == document_id
    assert payload["raw_markdown"] is None
