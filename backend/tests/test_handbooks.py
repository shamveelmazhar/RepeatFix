from app.handbooks import Heading, chunk_handbook, clean_page, handbook_id
from app.procedures import (
    Hit,
    ProcedureIndex,
    check_citations,
    chunk_files,
    citation,
    context_block,
    load_chunks,
    strip_unknown_citations,
    to_procedure,
)

# Page texts shaped like pypdf output of the AMT Handbook - Airframe: a chapter
# opener, figure callouts and a caption in the middle of a sentence, two
# headings in a row, a heading wrapped onto two lines, and the printed page number.
PAGES = [
    "Front matter, no chapter yet.",
    "Chapter 13\nAircraft Landing Gear Systems\nLanding Gear Types\n"
    "Aircraft landing gear supports the entire weight of an aircraft\nduring landing and ground operations.\n"
    "Shock Struts\nServicing Shock Struts\nServicing is done with the aircraft on jacks and the strut\n"
    "Hydraulic fluid bleed hose\nExerciser jack\n"
    "Figure 13-26. Air trapped in shock strut hydraulic fluid is bled by\nexercising the strut.\n"
    "deflated before the valve core is removed.\n13-1",
    "Bleeding Shock Struts\nIt may be necessary to bleed a shock strut when air becomes trapped\n"
    "in the hydraulic fluid inside the strut.\n1. Jack the aircraft until the shock struts are fully\nextended.\n"
    "Landing Gear Alignment, Support, &\nRetraction\nRetractable landing gear consist of several components\n"
    "that enable it to function.\n13-2",
    "Glossary\nAbsolute humidity. Not a procedure.\nG-1",
]
OUTLINE = [
    Heading(0, "Chapter 13", 1),
    Heading(0, "Aircraft Landing Gear Systems", 1),
    Heading(0, "Landing Gear Types", 1),
    Heading(1, "Shock Struts", 1),
    Heading(2, "Servicing Shock Struts", 1),
    Heading(2, "Bleeding Shock Struts", 2),
    Heading(0, "Landing Gear Alignment, Support, & Retraction", 2),
    Heading(0, "Glossary", 3),
]


def chunks():
    return {c.title: c for c in chunk_handbook(PAGES, OUTLINE, "FAA-H-8083-31B")}


def test_clean_page_drops_callouts_and_pulls_out_captions():
    body, captions = clean_page(PAGES[1], {"shock struts", "servicing shock struts"})
    assert "Exerciser jack" not in body and "13-1" not in body and "Chapter 13" not in body
    assert "Shock Struts" in body and "Servicing Shock Struts" in body  # back-to-back headings survive
    assert captions == ["Figure 13-26. Air trapped in shock strut hydraulic fluid is bled by exercising the strut."]


def test_chunks_follow_bookmarks_with_chapter_heading_path_and_printed_page():
    by_title = chunks()
    # "Shock Struts" has no text of its own before the next heading, so it gets no chunk.
    assert list(by_title) == [
        "Landing Gear Types",
        "Servicing Shock Struts",
        "Bleeding Shock Struts",
        "Landing Gear Alignment, Support, & Retraction",
    ]
    bleed = by_title["Bleeding Shock Struts"]
    assert (bleed.ac_number, bleed.chapter, bleed.chapter_title) == ("FAA-H-8083-31B", "13", "Aircraft Landing Gear Systems")
    assert bleed.section_title == "Landing Gear Types > Shock Struts"
    assert (bleed.page, bleed.page_label) == (3, "13-2")
    assert bleed.text.startswith("It may be necessary")  # heading itself is not repeated
    assert "Retractable" not in bleed.text  # stops at the next heading
    assert by_title["Landing Gear Alignment, Support, & Retraction"].text.startswith("Retractable")

    servicing = by_title["Servicing Shock Struts"]
    # The caption sat mid-sentence; the sentence is whole again and the caption is kept at the end.
    assert "the strut deflated before the valve core" in servicing.text
    assert servicing.text.endswith("(Figure 13-26: Air trapped in shock strut hydraulic fluid is bled by exercising the strut)")
    assert all("Glossary" not in c.text for c in by_title.values())


def test_handbook_citation_and_procedure_shape():
    bleed = chunks()["Bleeding Shock Struts"]
    assert citation(bleed) == 'FAA-H-8083-31B, Chapter 13 (Aircraft Landing Gear Systems), "Bleeding Shock Struts", page 13-2'
    proc = to_procedure(bleed)
    assert {"doc", "section", "page", "snippet", "url", "page_label", "citation"} == set(proc)
    assert proc["doc"] == "FAA-H-8083-31B AMT Handbook – Airframe"
    assert proc["section"] == "Bleeding Shock Struts (Ch. 13: Aircraft Landing Gear Systems)"
    assert (proc["page"], proc["page_label"]) == (3, "13-2")


def test_handbook_citations_are_checked_against_retrieved_pages():
    hits = [Hit(chunks()["Bleeding Shock Struts"], 1.0)]
    assert "[FAA-H-8083-31B p. 13-2]" in context_block(hits)
    answer = "Bleed the strut [FAA-H-8083-31B p. 13-2]. Check toe-in [FAA-H-8083-31B p. 13-15]."
    assert check_citations(answer, hits) == (["FAA-H-8083-31B p. 13-2"], ["FAA-H-8083-31B p. 13-15"])
    assert "13-15" not in strip_unknown_citations(answer, hits)


def test_handbook_id_from_file_name():
    assert handbook_id("FAA-H-8083-31B_Aviation_Maintenance_Technician_Handbook.pdf", []) == "FAA-H-8083-31B"
    assert handbook_id("Aviation Maintenance Technician Handbook - General (30B).pdf", []) == "FAA-H-8083-30B"


# ---- the committed chunks built from the real handbook PDFs


def test_committed_handbooks_cover_every_chapter():
    files = {p.stem for p in chunk_files()}
    assert {"ac_43-13-1b", "faa-h-8083-30b", "faa-h-8083-31b", "faa-h-8083-32b"} <= files
    chapters = {"faa-h-8083-30b": 14, "faa-h-8083-31b": 17, "faa-h-8083-32b": 11}
    for p in chunk_files():
        if p.stem not in chapters:
            continue
        chunks = load_chunks(p)
        assert {c.chapter for c in chunks} == {str(n) for n in range(1, chapters[p.stem] + 1)}
        assert len({c.paragraph for c in chunks}) > 700
        # The printed page number is chapter-relative and sits in the chunk's own chapter.
        assert all(c.page_label.split("-")[0] == c.chapter for c in chunks)
        assert len({c.id for c in chunks}) == len(chunks)


def test_search_finds_handbook_sections():
    index = ProcedureIndex.load()
    cases = {
        "nose strut low, air trapped in shock strut, bleed": ("FAA-H-8083-31B", "Bleeding Shock Struts", "13-14"),
        "propeller governor surging rpm": ("FAA-H-8083-32B", "Hunting & Surging", "7-30"),
        "engine hot start EGT exceeded on start": ("FAA-H-8083-30B", "Hot Start", "1-17"),
        "magneto timing off, rough running on left mag": ("FAA-H-8083-32B", "Timing the High-tension Magneto to the Engine", None),
    }
    for query, (doc, title, page) in cases.items():
        top = [(h.chunk.ac_number, h.chunk.title, h.chunk.page_label) for h in index.search(query, k=3)]
        assert any(d == doc and t == title and (page is None or p == page) for d, t, p in top), (query, top)


def test_search_can_mix_or_limit_documents():
    index = ProcedureIndex.load()
    mixed = {h.chunk.ac_number for h in index.search("tire worn in center, cut on sidewall", k=5)}
    assert {"AC 43.13-1B", "FAA-H-8083-31B"} <= mixed
    only = index.search("tire worn in center, cut on sidewall", k=5, docs={"FAA-H-8083-31B"})
    assert {h.chunk.ac_number for h in only} == {"FAA-H-8083-31B"}
