# Ed-Tech Exam Response Collator

Automatically collates student exam responses by question, combining them with mark schemes in a side-by-side layout for efficient marking.

## Overview

This tool processes exam materials and creates collated PDFs where:
- Student responses are grouped by question (not by student)
- Each output page shows student response on the left and mark scheme on the right
- Output is in landscape format for easy review
- Handles multi-page questions and mark schemes automatically

## Directory Structure

Place your exam materials in the following standardized directories:

```
inputs/
├── mark-scheme/          # Place mark scheme PDF here
├── page-mapping/         # Place page mapping CSV here
├── question-paper/       # Place question paper PDF here
└── student-responses/    # Place all student response PDFs here
```

The script will automatically discover files in these directories.

### Page Mapping CSV Format

Your CSV in `inputs/page-mapping/` should have these columns:
- `Q` - Question ID (e.g., "1a", "2b(i)")
- `Topic` - Topic name
- `Question Page Map` - Page number(s) in question paper (e.g., "5" or "8-9")
- `Mark scheme page map` - Page number(s) in mark scheme (e.g., "12" or "15-16")
- `Max marks` - Maximum marks for the question

## Installation

1. Install Python 3.7 or higher
2. Install dependencies:

```bash
pip install -r requirements.txt
```

## Usage

1. Place your exam materials in the `inputs/` directories (see structure above)
2. Run the collation script:

```bash
python collate_responses.py
```

3. Find collated PDFs in the `outputs/` directory:
   - `Q1.pdf` - All students' responses to Question 1 (all sub-parts)
   - `Q2.pdf` - All students' responses to Question 2 (all sub-parts)
   - `Q3.pdf` through `Q7.pdf` - Remaining questions
   - `Extra_space.pdf` - All extra space pages (2 students per page)

## Features

- **Automatic file discovery** - No need to hardcode filenames
- **Reusable** - Works with any exam following the directory structure
- **Multi-page handling** - Handles questions and mark schemes spanning multiple pages
- **Landscape layout** - 60/40 split (student response / mark scheme)
- **Question grouping** - Sub-questions grouped by main question number
- **Student identification** - Each page shows student name and question number
- **Extra space collection** - Automatically collates extra work pages in 2-up format

## Output Format

### Question PDFs (Q1.pdf - Q7.pdf)
Each output PDF contains:
- One page per student per question page
- Student response on the left (60% width)
- Mark scheme on the right (40% width)
- Multi-page mark schemes stacked vertically on the right side
- Student name overlay at bottom left (e.g., "Anmoldeep Question 1 (page 1/2)")

### Extra Space PDF (Extra_space.pdf)
- Two student pages side-by-side in landscape format (50/50 split)
- Collects all pages after the last question from each student
- Student name overlay on each page (e.g., "Harmanpreet Extra Space")

## Notes

- Student response PDFs should follow the same page order as the question paper
- The `student-responses/` directory is gitignored for privacy
- The `outputs/` directory is created automatically
