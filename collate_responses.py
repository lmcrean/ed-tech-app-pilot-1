#!/usr/bin/env python3
"""
PDF Response Collation Script

Automatically discovers and processes exam materials from standardized input directories:
- inputs/mark-scheme/
- inputs/page-mapping/
- inputs/question-paper/
- inputs/student-responses/

Outputs collated PDFs by question (Q1.pdf, Q2.pdf, etc.) with student responses on the left
and mark schemes on the right in landscape format.
"""

import os
import sys
from pathlib import Path
import pandas as pd
import fitz  # PyMuPDF
import re
from collections import defaultdict


class ExamCollator:
    def __init__(self, base_dir=None):
        """Initialize the collator with the base directory containing inputs/"""
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).parent
        self.inputs_dir = self.base_dir / "inputs"
        self.outputs_dir = self.base_dir / "outputs"

        # Auto-discovered file paths
        self.mark_scheme_pdf = None
        self.question_paper_pdf = None
        self.page_mapping_csv = None
        self.student_pdfs = []

        # Parsed data
        self.page_map_df = None
        self.questions_by_main = defaultdict(list)

    def discover_inputs(self):
        """Auto-discover input files from standard directory structure"""
        print("🔍 Discovering input files...")

        # Find mark scheme PDF
        mark_scheme_dir = self.inputs_dir / "mark-scheme"
        mark_scheme_pdfs = list(mark_scheme_dir.glob("*.pdf"))
        if not mark_scheme_pdfs:
            raise FileNotFoundError(f"No PDF found in {mark_scheme_dir}")
        self.mark_scheme_pdf = mark_scheme_pdfs[0]
        print(f"  ✓ Mark scheme: {self.mark_scheme_pdf.name}")

        # Find question paper PDF
        question_paper_dir = self.inputs_dir / "question-paper"
        question_paper_pdfs = list(question_paper_dir.glob("*.pdf"))
        if not question_paper_pdfs:
            raise FileNotFoundError(f"No PDF found in {question_paper_dir}")
        self.question_paper_pdf = question_paper_pdfs[0]
        print(f"  ✓ Question paper: {self.question_paper_pdf.name}")

        # Find page mapping CSV
        page_mapping_dir = self.inputs_dir / "page-mapping"
        page_mapping_csvs = list(page_mapping_dir.glob("*.csv"))
        if not page_mapping_csvs:
            raise FileNotFoundError(f"No CSV found in {page_mapping_dir}")
        self.page_mapping_csv = page_mapping_csvs[0]
        print(f"  ✓ Page mapping: {self.page_mapping_csv.name}")

        # Find all student response PDFs
        student_responses_dir = self.inputs_dir / "student-responses"
        self.student_pdfs = sorted(list(student_responses_dir.glob("*.pdf")))
        if not self.student_pdfs:
            raise FileNotFoundError(f"No student PDFs found in {student_responses_dir}")
        print(f"  ✓ Found {len(self.student_pdfs)} student response PDFs")

    def parse_page_mapping(self):
        """Parse the page mapping CSV and group questions by main number"""
        print(f"\n📊 Parsing page mapping...")

        self.page_map_df = pd.read_csv(self.page_mapping_csv)

        # Group questions by main question number (Q1, Q2, etc.)
        for _, row in self.page_map_df.iterrows():
            q_id = row['Q']
            # Extract main question number (e.g., "1" from "1a", "2" from "2a(i)")
            main_q = re.match(r'^(\d+)', q_id).group(1)
            self.questions_by_main[f"Q{main_q}"].append(row)

        print(f"  ✓ Grouped into {len(self.questions_by_main)} main questions")
        for main_q in sorted(self.questions_by_main.keys()):
            sub_questions = [row['Q'] for row in self.questions_by_main[main_q]]
            print(f"    {main_q}: {', '.join(sub_questions)}")

    def parse_page_range(self, page_str):
        """Parse page range string (e.g., '8', '8-9') into list of page numbers"""
        if pd.isna(page_str):
            return []
        page_str = str(page_str).strip()
        if '-' in page_str:
            start, end = map(int, page_str.split('-'))
            return list(range(start, end + 1))
        else:
            return [int(page_str)]

    def create_landscape_page(self, student_page, mark_scheme_pages, output_pdf):
        """
        Create a landscape page with student response on left and mark scheme on right

        Args:
            student_page: fitz.Page object for student response
            mark_scheme_pages: list of fitz.Page objects for mark scheme
            output_pdf: fitz.Document to add the new page to
        """
        # Standard page sizes (A4)
        A4_WIDTH = 595  # points
        A4_HEIGHT = 842  # points

        # Landscape dimensions
        landscape_width = A4_HEIGHT  # 842
        landscape_height = A4_WIDTH  # 595

        # Create new landscape page
        new_page = output_pdf.new_page(width=landscape_width, height=landscape_height)

        # Calculate dimensions for 60/40 split
        left_width = landscape_width * 0.6  # ~505 points
        right_width = landscape_width * 0.4  # ~337 points

        # Place student response on left side
        student_rect = fitz.Rect(0, 0, left_width, landscape_height)
        new_page.show_pdf_page(student_rect, student_page.parent, student_page.number)

        # Place mark scheme(s) on right side
        if len(mark_scheme_pages) == 1:
            # Single mark scheme page - use full right side
            ms_rect = fitz.Rect(left_width, 0, landscape_width, landscape_height)
            new_page.show_pdf_page(ms_rect, mark_scheme_pages[0].parent, mark_scheme_pages[0].number)
        elif len(mark_scheme_pages) == 2:
            # Two mark scheme pages - stack vertically
            ms_height = landscape_height / 2
            ms_rect_top = fitz.Rect(left_width, 0, landscape_width, ms_height)
            ms_rect_bottom = fitz.Rect(left_width, ms_height, landscape_width, landscape_height)
            new_page.show_pdf_page(ms_rect_top, mark_scheme_pages[0].parent, mark_scheme_pages[0].number)
            new_page.show_pdf_page(ms_rect_bottom, mark_scheme_pages[1].parent, mark_scheme_pages[1].number)

        return new_page

    def collate_question(self, main_q_id, question_rows):
        """
        Collate all student responses for a main question

        Args:
            main_q_id: Main question ID (e.g., "Q1")
            question_rows: List of row dicts containing question data
        """
        print(f"\n📝 Processing {main_q_id}...")

        # Collect all question pages and mark scheme pages for this main question
        all_question_pages = set()
        all_mark_scheme_pages = set()

        for row in question_rows:
            q_pages = self.parse_page_range(row['Question Page Map'])
            ms_pages = self.parse_page_range(row['Mark scheme page map'])
            all_question_pages.update(q_pages)
            all_mark_scheme_pages.update(ms_pages)

        all_question_pages = sorted(list(all_question_pages))
        all_mark_scheme_pages = sorted(list(all_mark_scheme_pages))

        print(f"  Question pages: {all_question_pages}")
        print(f"  Mark scheme pages: {all_mark_scheme_pages}")

        # Open mark scheme PDF
        mark_scheme_doc = fitz.open(self.mark_scheme_pdf)

        # Get mark scheme pages (convert to 0-indexed)
        mark_scheme_page_objs = [mark_scheme_doc[p - 1] for p in all_mark_scheme_pages]

        # Create output PDF
        output_pdf = fitz.open()

        # Process each student
        for student_pdf_path in self.student_pdfs:
            student_name = student_pdf_path.stem
            student_doc = fitz.open(student_pdf_path)

            # Extract student pages for this question (convert to 0-indexed)
            for q_page_num in all_question_pages:
                if q_page_num - 1 < len(student_doc):
                    student_page = student_doc[q_page_num - 1]

                    # Create landscape page with student response and mark scheme
                    self.create_landscape_page(student_page, mark_scheme_page_objs, output_pdf)

            student_doc.close()

        # Save output PDF
        output_path = self.outputs_dir / f"{main_q_id}.pdf"
        output_pdf.save(str(output_path))
        output_pdf.close()
        mark_scheme_doc.close()

        print(f"  ✅ Saved {output_path.name} ({len(output_pdf)} pages)")

    def collate_all(self):
        """Collate all questions"""
        # Create outputs directory if it doesn't exist
        self.outputs_dir.mkdir(exist_ok=True)

        print(f"\n{'='*60}")
        print("🚀 Starting collation process...")
        print(f"{'='*60}")

        # Process each main question
        for main_q_id in sorted(self.questions_by_main.keys()):
            self.collate_question(main_q_id, self.questions_by_main[main_q_id])

        print(f"\n{'='*60}")
        print("✨ Collation complete!")
        print(f"{'='*60}")
        print(f"Output files saved to: {self.outputs_dir}")

    def run(self):
        """Main execution flow"""
        try:
            self.discover_inputs()
            self.parse_page_mapping()
            self.collate_all()
        except Exception as e:
            print(f"\n❌ Error: {e}", file=sys.stderr)
            raise


def main():
    """Entry point for the script"""
    collator = ExamCollator()
    collator.run()


if __name__ == "__main__":
    main()
