#!/bin/bash

# ArXiv Paper Tracker - Interactive Tool for macOS/Linux

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT" || exit 1

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    exit 1
fi

# Function to display menu
show_menu() {
    clear
    echo "========================================"
    echo "arXiv Paper Tracker - Interactive Tool"
    echo "========================================"
    echo ""
    echo "Please select an operation:"
    echo "  1. Run full analysis"
    echo "  2. Analyze single paper (arXiv ID)"
    echo "  3. Analyze local PDF"
    echo "  4. Exit"
    echo ""
}

# Function to run full analysis
run_all() {
    echo "=== Running Full Analysis ==="
    python3 src/main.py
    echo "Operation completed."
    read -p "Press Enter to continue..."
}

# Function to analyze single paper
run_single() {
    echo "=== Single Paper Analysis (arXiv ID) ==="
    read -p "Enter arXiv ID (e.g., 2305.09582): " arxiv_id
    if [ -z "$arxiv_id" ]; then
        echo "arXiv ID cannot be empty."
        read -p "Press Enter to continue..."
        return
    fi
    read -p "Enter number of pages to extract (default 10, or 'all'): " pages
    if [ -z "$pages" ]; then
        pages=10
    fi
    python3 src/main.py --arxiv "$arxiv_id" -p "$pages"
    echo "Operation completed."
    read -p "Press Enter to continue..."
}

# Function to analyze local PDF
run_local_pdf() {
    echo "=== Local PDF Analysis ==="

    if [ ! -d "papers" ]; then
        echo "Papers folder not found. Creating 'papers' folder..."
        mkdir papers
        echo "Please put your PDF files in the 'papers' folder and try again."
        read -p "Press Enter to continue..."
        return
    fi

    echo ""
    echo "Available PDF files in 'papers' folder:"
    echo ""

    # Count PDF files
    count=0
    pdf_files=()
    for pdf in papers/*.pdf; do
        if [ -f "$pdf" ]; then
            count=$((count + 1))
            pdf_files+=("$pdf")
            echo "  $count. $(basename "$pdf")"
        fi
    done

    if [ $count -eq 0 ]; then
        echo "No PDF files found in 'papers' folder."
        echo "Please put your PDF files in the 'papers' folder and try again."
        read -p "Press Enter to continue..."
        return
    fi

    echo ""
    read -p "Enter the number of PDF to analyze (0 to cancel): " pdf_choice

    if [ "$pdf_choice" = "0" ]; then
        return
    fi

    if [ "$pdf_choice" -lt 1 ] || [ "$pdf_choice" -gt $count ]; then
        echo "Invalid choice, please try again."
        read -p "Press Enter to continue..."
        return
    fi

    selected_pdf="${pdf_files[$((pdf_choice - 1))]}"
    echo "Selected: $(basename "$selected_pdf")"
    echo ""

    read -p "Enter number of pages to extract (default 10, or 'all'): " pages
    if [ -z "$pages" ]; then
        pages=10
    fi

    python3 src/main.py --pdf "$selected_pdf" -p "$pages"
    echo "Operation completed."
    read -p "Press Enter to continue..."
}

# Main loop
while true; do
    show_menu
    read -p "Enter your choice (1-4): " choice

    case $choice in
        1)
            run_all
            ;;
        2)
            run_single
            ;;
        3)
            run_local_pdf
            ;;
        4)
            echo "Thank you for using!"
            exit 0
            ;;
        *)
            echo "Invalid choice, please try again."
            read -p "Press Enter to continue..."
            ;;
    esac
done
