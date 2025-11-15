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
        print("Discovering input files...")

        # Find mark scheme PDF
        mark_scheme_dir = self.inputs_dir / "mark-scheme"
        mark_scheme_pdfs = list(mark_scheme_dir.glob("*.pdf"))
        if not mark_scheme_pdfs:
            raise FileNotFoundError(f"No PDF found in {mark_scheme_dir}")
        self.mark_scheme_pdf = mark_scheme_pdfs[0]
        print(f"  [OK] Mark scheme: {self.mark_scheme_pdf.name}")

        # Find question paper PDF
        question_paper_dir = self.inputs_dir / "question-paper"
        question_paper_pdfs = list(question_paper_dir.glob("*.pdf"))
        if not question_paper_pdfs:
            raise FileNotFoundError(f"No PDF found in {question_paper_dir}")
        self.question_paper_pdf = question_paper_pdfs[0]
        print(f"  [OK] Question paper: {self.question_paper_pdf.name}")

        # Find page mapping CSV
        page_mapping_dir = self.inputs_dir / "page-mapping"
        page_mapping_csvs = list(page_mapping_dir.glob("*.csv"))
        if not page_mapping_csvs:
            raise FileNotFoundError(f"No CSV found in {page_mapping_dir}")
        self.page_mapping_csv = page_mapping_csvs[0]
        print(f"  [OK] Page mapping: {self.page_mapping_csv.name}")

        # Find all student response PDFs
        student_responses_dir = self.inputs_dir / "student-responses"
        self.student_pdfs = sorted(list(student_responses_dir.glob("*.pdf")))
        if not self.student_pdfs:
            raise FileNotFoundError(f"No student PDFs found in {student_responses_dir}")
        print(f"  [OK] Found {len(self.student_pdfs)} student response PDFs")

    def parse_page_mapping(self):
        """Parse the page mapping CSV and group questions by main number"""
        print(f"\nParsing page mapping...")

        # Try to read as tab-separated, fallback to comma-separated
        try:
            self.page_map_df = pd.read_csv(self.page_mapping_csv, sep='\t')
        except:
            self.page_map_df = pd.read_csv(self.page_mapping_csv)

        # Group questions by main question number (Q1, Q2, etc.)
        for _, row in self.page_map_df.iterrows():
            q_id = str(row['Q']).strip()
            # Skip rows that don't start with a digit (like TOTAL row)
            match = re.match(r'^(\d+)', q_id)
            if not match:
                continue
            # Extract main question number (e.g., "1" from "1a", "2" from "2a(i)")
            main_q = match.group(1)
            self.questions_by_main[f"Q{main_q}"].append(row)

        print(f"  [OK] Grouped into {len(self.questions_by_main)} main questions")
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

    def create_landscape_page(self, student_page, mark_scheme_pages, output_pdf, student_name, question_label, page_info=""):
        """
        Create a landscape page with student response on left and mark scheme on right

        Args:
            student_page: fitz.Page object for student response
            mark_scheme_pages: list of fitz.Page objects for mark scheme
            output_pdf: fitz.Document to add the new page to
            student_name: Name of the student
            question_label: Question identifier (e.g., "Question 1", "Question 4")
            page_info: Optional page info (e.g., "(part 1/3)")
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

        # Add student identification overlay at the bottom
        # Create semi-transparent dark background bar
        bar_height = 40
        bar_rect = fitz.Rect(0, landscape_height - bar_height, left_width, landscape_height)

        # Draw semi-transparent dark gray rectangle
        shape = new_page.new_shape()
        shape.draw_rect(bar_rect)
        shape.finish(fill=(0.3, 0.3, 0.3), fill_opacity=0.85)
        shape.commit()

        # Add text label
        label_text = f"{student_name} {question_label}"
        if page_info:
            label_text += f" {page_info}"

        # Insert text in white using built-in Helvetica font
        text_point = fitz.Point(10, landscape_height - 12)  # 10px from left, 12px from bottom
        new_page.insert_text(
            text_point,
            label_text,
            fontsize=14,
            fontname="helv",
            color=(1, 1, 1)  # White text
        )

        return new_page

    def collate_question(self, main_q_id, question_rows):
        """
        Collate all student responses for a main question

        Args:
            main_q_id: Main question ID (e.g., "Q1")
            question_rows: List of row dicts containing question data
        """
        print(f"\nProcessing {main_q_id}...")

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

            # Collect valid pages for this student first to determine total count
            student_pages_to_process = []
            for q_page_num in all_question_pages:
                if q_page_num - 1 < len(student_doc):
                    student_pages_to_process.append((q_page_num, student_doc[q_page_num - 1]))

            total_pages = len(student_pages_to_process)
            question_label = f"Question {main_q_id[1:]}"  # Remove 'Q' prefix

            # Process each page for this student
            for page_idx, (q_page_num, student_page) in enumerate(student_pages_to_process, start=1):
                # Determine page info string
                if total_pages > 1:
                    page_info = f"(page {page_idx}/{total_pages})"
                else:
                    page_info = ""

                # Create landscape page with student response and mark scheme
                self.create_landscape_page(
                    student_page,
                    mark_scheme_page_objs,
                    output_pdf,
                    student_name,
                    question_label,
                    page_info
                )

            student_doc.close()

        # Save output PDF
        output_path = self.outputs_dir / f"{main_q_id}.pdf"
        page_count = len(output_pdf)
        output_pdf.save(str(output_path))
        output_pdf.close()
        mark_scheme_doc.close()

        print(f"  [DONE] Saved {output_path.name} ({page_count} pages)")

    def create_two_up_landscape_page(self, page1, page2, output_pdf, student1_name, student2_name=None):
        """
        Create a landscape page with two student pages side-by-side

        Args:
            page1: fitz.Page object for left student page
            page2: fitz.Page object for right student page (can be None)
            output_pdf: fitz.Document to add the new page to
            student1_name: Name of the first student (left)
            student2_name: Name of the second student (right, optional)
        """
        # Standard page sizes (A4)
        A4_WIDTH = 595  # points
        A4_HEIGHT = 842  # points

        # Landscape dimensions
        landscape_width = A4_HEIGHT  # 842
        landscape_height = A4_WIDTH  # 595

        # Create new landscape page
        new_page = output_pdf.new_page(width=landscape_width, height=landscape_height)

        # Calculate dimensions for 50/50 split
        half_width = landscape_width / 2  # ~421 points

        # Place first student page on left side
        left_rect = fitz.Rect(0, 0, half_width, landscape_height)
        new_page.show_pdf_page(left_rect, page1.parent, page1.number)

        # Add label for first student
        self._add_label_to_rect(new_page, left_rect, student1_name, "Extra Space")

        # Place second student page on right side (if provided)
        if page2:
            right_rect = fitz.Rect(half_width, 0, landscape_width, landscape_height)
            new_page.show_pdf_page(right_rect, page2.parent, page2.number)

            if student2_name:
                self._add_label_to_rect(new_page, right_rect, student2_name, "Extra Space")

        return new_page

    def _add_label_to_rect(self, page, rect, student_name, label):
        """Helper to add a label overlay to a specific rectangle area"""
        bar_height = 40
        bar_rect = fitz.Rect(rect.x0, rect.y1 - bar_height, rect.x1, rect.y1)

        # Draw semi-transparent dark gray rectangle
        shape = page.new_shape()
        shape.draw_rect(bar_rect)
        shape.finish(fill=(0.3, 0.3, 0.3), fill_opacity=0.85)
        shape.commit()

        # Add text label
        label_text = f"{student_name} {label}"

        # Insert text in white
        text_point = fitz.Point(rect.x0 + 10, rect.y1 - 12)
        page.insert_text(
            text_point,
            label_text,
            fontsize=14,
            fontname="helv",
            color=(1, 1, 1)
        )

    def collate_extra_space(self):
        """Collate all extra space pages (pages after the last question)"""
        print(f"\nProcessing Extra Space pages...")

        # Determine the last question page from the page mapping
        max_question_page = 0
        for _, row in self.page_map_df.iterrows():
            q_pages = self.parse_page_range(row['Question Page Map'])
            if q_pages:
                max_question_page = max(max_question_page, max(q_pages))

        print(f"  Last question page: {max_question_page}")

        # Create output PDF
        output_pdf = fitz.open()

        # Collect extra space pages from all students
        extra_space_pages = []

        for student_pdf_path in self.student_pdfs:
            student_name = student_pdf_path.stem
            student_doc = fitz.open(student_pdf_path)

            # Get all pages after the last question page
            for page_num in range(max_question_page, len(student_doc)):
                extra_space_pages.append({
                    'page': student_doc[page_num],
                    'student_name': student_name,
                    'doc': student_doc  # Keep reference to prevent closing
                })

        print(f"  Found {len(extra_space_pages)} extra space pages across all students")

        # Create 2-up layout pages
        for i in range(0, len(extra_space_pages), 2):
            page1_info = extra_space_pages[i]
            page2_info = extra_space_pages[i + 1] if i + 1 < len(extra_space_pages) else None

            self.create_two_up_landscape_page(
                page1_info['page'],
                page2_info['page'] if page2_info else None,
                output_pdf,
                page1_info['student_name'],
                page2_info['student_name'] if page2_info else None
            )

        # Close all student documents
        closed_docs = set()
        for page_info in extra_space_pages:
            if id(page_info['doc']) not in closed_docs:
                page_info['doc'].close()
                closed_docs.add(id(page_info['doc']))

        # Save output PDF
        if len(output_pdf) > 0:
            output_path = self.outputs_dir / "Extra_space.pdf"
            page_count = len(output_pdf)
            output_pdf.save(str(output_path))
            output_pdf.close()
            print(f"  [DONE] Saved {output_path.name} ({page_count} pages, {len(extra_space_pages)} student pages)")
        else:
            output_pdf.close()
            print(f"  [SKIP] No extra space pages found")

    def collate_all(self):
        """Collate all questions"""
        # Create outputs directory if it doesn't exist
        self.outputs_dir.mkdir(exist_ok=True)

        print(f"\n{'='*60}")
        print("Starting collation process...")
        print(f"{'='*60}")

        # Process each main question
        for main_q_id in sorted(self.questions_by_main.keys()):
            self.collate_question(main_q_id, self.questions_by_main[main_q_id])

        # Process extra space pages
        self.collate_extra_space()

        print(f"\n{'='*60}")
        print("Collation complete!")
        print(f"{'='*60}")
        print(f"Output files saved to: {self.outputs_dir}")

    def run(self):
        """Main execution flow"""
        try:
            self.discover_inputs()
            self.parse_page_mapping()
            self.collate_all()
        except Exception as e:
            print(f"\n[ERROR] {e}", file=sys.stderr)
            raise


def main():
    """Entry point for the script"""
    collator = ExamCollator()
    collator.run()


if __name__ == "__main__":
    main()
