from app.procedures import (
    DEFAULT_CHUNKS,
    Hit,
    ProcedureIndex,
    check_citations,
    chunk_pages,
    citation,
    context_block,
    load_chunks,
    strip_unknown_citations,
    to_procedure,
    tokenize,
)

# Page texts shaped like pypdf output of AC 43.13-1B: header, "Par/Page" footer
# near the top, a paragraph number broken across lines, a wrapped section title,
# a cross-reference that must not start a new paragraph, and a reserved range.
PAGES = [
    "9/8/98  AC 43.13-1B\nCONTENTS\n9-14. TIRE INSPECTION AND REPAIR ........ 9-12\n",
    "9/8/98  AC 43.13-1B \nPar 9-1 Page 9-1 \nCHAPTER 9.  AIRCRAFT SYSTEMS AND COMPONENTS \n"
    "SECTION 1.  INSPECTION AND MAINTENANCE OF \nLANDING GEAR \n"
    "9-1. GENERAL. Landing gear may be fixed or retractable. \n"
    "9-2. See paragraph 9-1 for gear types and inspect the brake. \n"
    "9-\n14. TIRE INSPECTION AND REPAIR. Tires should be inspected frequently for cuts, worn \n"
    "spots, bulges on the side walls, and tread condition. \n",
    "9/27/01  AC 43.13-1B CHG 1 \nPar 9-14 Page 9-2 \n"
    "g. Surface Condition. If the tread is worn in the center of the tire but not on the edges, the tire is overinflated. \n"
    "9-15.–9-24. [RESERVED.] \n"
    "SECTION 2.  HYDRAULIC SYSTEMS \n"
    "9-25.\n GENERAL. Hydraulic fluid leaks at fittings should be found and fixed. \n",
    "9/27/01  AC 43.13-1B CHG 1 \n  Appendix 1 \nPage 8 \nGlossary text that is not a paragraph. \n",
]


def test_chunks_carry_ac_chapter_section_paragraph_and_page():
    chunks = chunk_pages(PAGES)
    by_para = {c.paragraph: c for c in chunks}
    assert list(by_para) == ["9-1", "9-14", "9-25"]  # 9-2 is a cross-reference, front matter skipped

    tire = by_para["9-14"]
    assert tire.ac_number == "AC 43.13-1B"
    assert (tire.chapter, tire.chapter_title) == ("9", "Aircraft Systems and Components")
    assert (tire.section, tire.section_title) == ("1", "Inspection and Maintenance of Landing Gear")
    assert tire.title == "Tire Inspection and Repair"
    assert (tire.page, tire.page_label) == (2, "9-1")
    assert "overinflated" in tire.text  # text continues across the page turn
    assert "RESERVED" not in tire.text and "Par 9-14" not in tire.text

    hyd = by_para["9-25"]
    assert (hyd.section, hyd.section_title, hyd.page_label) == ("2", "Hydraulic Systems", "9-2")
    assert "Glossary" not in hyd.text  # parsing stops at the appendix


def test_long_paragraph_parts_cite_the_page_they_start_on():
    body = " ".join(f"Sentence {i} about cable wear and broken wires." for i in range(60))
    pages = [
        f"Par 7-149 Page 7-39\n7-149. CABLE SYSTEM INSPECTION. {body}\n",
        f"Par 7-149 Page 7-40\nm. Pulleys. {body}\n",
    ]
    chunks = chunk_pages(pages)
    assert len(chunks) > 2 and {c.paragraph for c in chunks} == {"7-149"}
    assert chunks[0].page_label == "7-39" and chunks[-1].page_label == "7-40"
    assert all(len(c.text) <= 2000 for c in chunks)
    assert [c.part for c in chunks] == list(range(1, len(chunks) + 1))


def test_tokenize_expands_shop_shorthand():
    assert tokenize("#2 brk dragging, hyd lkg") == ["brake", "drag", "hydraulic", "leak"]


def test_citation_and_procedure_shape():
    tire = {c.paragraph: c for c in chunk_pages(PAGES)}["9-14"]
    assert citation(tire) == (
        "AC 43.13-1B, Chapter 9, Section 1, par. 9-14 (Tire Inspection and Repair), page 9-1"
    )
    proc = to_procedure(tire)
    # docs/API.md: procedures[] = { doc, section, page, snippet, url? } (+ page_label, citation)
    assert {"doc", "section", "page", "snippet", "url", "page_label", "citation"} == set(proc)
    assert proc["section"].startswith("Par. 9-14 Tire Inspection and Repair")
    assert isinstance(proc["page"], int)
    assert not proc["snippet"].startswith("9-14.")


def test_answer_citations_are_checked_against_retrieved_paragraphs():
    chunks = chunk_pages(PAGES)
    hits = [Hit(c, 1.0) for c in chunks if c.paragraph == "9-14"]
    assert "[AC 43.13-1B par. 9-14]" in context_block(hits)
    answer = "Inspect the tread [AC 43.13-1B par. 9-14]. Re-torque the axle nut [AC 43.13-1B par. 9-99]."
    assert check_citations(answer, hits) == (["9-14"], ["9-99"])
    assert "9-99" not in strip_unknown_citations(answer, hits)
    assert "[AC 43.13-1B par. 9-14]" in strip_unknown_citations(answer, hits)


# ---- the committed index built from the real AC 43.13-1B CHG 1 PDF


def test_committed_index_covers_every_chapter():
    chunks = load_chunks(DEFAULT_CHUNKS)
    assert len({c.paragraph for c in chunks}) >= 650
    assert {c.chapter for c in chunks} == {str(n) for n in range(1, 14)}
    assert all(c.page_label and c.ac_number == "AC 43.13-1B" for c in chunks)


def test_search_finds_the_right_ac_paragraph():
    index = ProcedureIndex.load()
    cases = {
        "tire worn in center, cut on sidewall": "9-14",
        "rudder control cable frayed at pulley, broken wires": "7-149",
        "hyd pump leaking at case drain fitting": "9-29",
        "nicad battery overheated and venting": "11-19",
        "oxygen cylinder hydrostatic test due": "9-51",
        "exhaust stack crack": "8-47",
    }
    for query, para in cases.items():
        top = [h.chunk.paragraph for h in index.search(query, k=3)]
        assert para in top, (query, top)


def test_search_returns_one_hit_per_paragraph():
    hits = ProcedureIndex.load().search("brake dragging, temperature high after taxi", k=5)
    paras = [h.chunk.paragraph for h in hits]
    assert len(paras) == len(set(paras)) == 5
    assert "9-7" in paras[:2]  # Landing-gear components: brakes
