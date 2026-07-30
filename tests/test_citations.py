import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from citations import (  # noqa: E402
    build_payload,
    collect_answer,
    extract_citations,
    format_citation_list,
    strip_markers,
)


class FakeBlock:
    def __init__(self, type_: str, text: str = "") -> None:
        self.type = type_
        self.text = text


class FakeEvent:
    def __init__(self, type_: str, content=None) -> None:
        self.type = type_
        self.content = content


class ExtractCitationsTests(unittest.TestCase):
    def test_extracts_documents_and_memory_paths_in_order(self) -> None:
        text = (
            "You need a sponsor [[cite: access-policy.md]] and two weeks tenure "
            "[[cite: /mnt/memory/policies.md]]."
        )
        citations = extract_citations(text)

        self.assertEqual([c["source"] for c in citations], [
            "access-policy.md",
            "/mnt/memory/policies.md",
        ])
        self.assertEqual([c["kind"] for c in citations], ["document", "memory"])
        self.assertEqual([c["index"] for c in citations], [1, 2])

    def test_dedupes_repeated_source_and_counts_uses(self) -> None:
        text = "A [[cite: a.md]] B [[cite: a.md]] C [[cite: b.md]]"
        citations = extract_citations(text)

        self.assertEqual(len(citations), 2)
        self.assertEqual(citations[0]["count"], 2)
        self.assertEqual(citations[1]["count"], 1)
        self.assertEqual(citations[1]["index"], 2)

    def test_tolerates_whitespace_and_case_variants(self) -> None:
        text = "X [[Cite:  team-directory.md  ]] Y [[ cite :\tnotes.md ]]"
        self.assertEqual(
            [c["source"] for c in extract_citations(text)],
            ["team-directory.md", "notes.md"],
        )

    def test_returns_empty_for_uncited_text(self) -> None:
        self.assertEqual(extract_citations("No attribution here."), [])
        self.assertEqual(extract_citations(""), [])


class StripMarkersTests(unittest.TestCase):
    def test_removes_markers_and_tidies_spacing(self) -> None:
        text = "Ask the on-call SRE [[cite: access-policy.md]] first."
        self.assertEqual(strip_markers(text), "Ask the on-call SRE first.")

    def test_does_not_leave_space_before_punctuation(self) -> None:
        text = "Sponsor approval is required [[cite: a.md]]."
        self.assertEqual(strip_markers(text), "Sponsor approval is required.")

    def test_preserves_line_structure(self) -> None:
        text = "- one [[cite: a.md]]\n- two [[cite: b.md]]"
        self.assertEqual(strip_markers(text), "- one\n- two")


class PayloadTests(unittest.TestCase):
    def test_build_payload_separates_prose_from_citations(self) -> None:
        payload = build_payload("Do X [[cite: access-policy.md]].")

        self.assertEqual(payload["answer"], "Do X.")
        self.assertIn("[[cite:", payload["answer_with_markers"])
        self.assertTrue(payload["has_citations"])
        self.assertEqual(payload["citations"][0]["source"], "access-policy.md")

    def test_build_payload_flags_missing_citations(self) -> None:
        payload = build_payload("Unattributed claim.")

        self.assertFalse(payload["has_citations"])
        self.assertEqual(payload["citations"], [])
        self.assertEqual(payload["answer"], "Unattributed claim.")


class CollectAnswerTests(unittest.TestCase):
    def test_concatenates_only_agent_message_text_blocks(self) -> None:
        events = [
            FakeEvent("agent.tool_use", content=None),
            FakeEvent("agent.message", content=[FakeBlock("text", "Hello ")]),
            FakeEvent("agent.message", content=[
                FakeBlock("thinking", "ignored"),
                FakeBlock("text", "world"),
            ]),
            FakeEvent("session.status_idle", content=None),
        ]
        self.assertEqual(collect_answer(events), "Hello world")

    def test_handles_events_without_content(self) -> None:
        self.assertEqual(collect_answer([FakeEvent("agent.message")]), "")


class FormatCitationListTests(unittest.TestCase):
    def test_renders_numbered_list(self) -> None:
        citations = extract_citations("A [[cite: a.md]] B [[cite: a.md]]")
        self.assertEqual(
            format_citation_list(citations),
            "[1] a.md  (document, 2x)",
        )

    def test_explains_absence_of_citations(self) -> None:
        self.assertIn("none", format_citation_list([]))


if __name__ == "__main__":
    unittest.main()
