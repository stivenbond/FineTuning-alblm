import os

# --- Configuration Constants ---
# Change these paths to match your local environment
PROMPT_DIR = "C:\\Users\\stive\\Projects\\Thesis\\Lahuta\\models\\albanian_analysis\\prompts"
ARTICLE_DIR = "C:\\Users\\stive\\Projects\\Thesis\\Lahuta\\models\\albanian_analysis\\data\\seed_article_text"
OUTPUT_DIR = "C:\\Users\\stive\\Projects\\Thesis\\Lahuta\\models\\albanian_analysis\\data\\raw_synthetic_reports"

# File naming patterns (e.g., "1.txt", "2.txt" or "prompt_1.txt")
PROMPT_PREFIX = "article_to_report" 
ARTICLE_PREFIX = "article_"
OUTPUT_PREFIX = "report_"

FILE_EXTENSION = ".txt"

# Range of files to process
START_INDEX = 1
END_INDEX = 65 

def process_sequential_files():
    # Ensure output directory exists
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"Created directory: {OUTPUT_DIR}")

    for i in range(START_INDEX, END_INDEX + 1):
        # Construct file names
        prompt_filename = f"{PROMPT_PREFIX}{FILE_EXTENSION}"
        article_filename = f"{ARTICLE_PREFIX}{i}{FILE_EXTENSION}"
        output_filename = f"{OUTPUT_PREFIX}{i}{FILE_EXTENSION}"

        # Build full paths
        prompt_path = os.path.join(PROMPT_DIR, prompt_filename)
        article_path = os.path.join(ARTICLE_DIR, article_filename)
        output_path = os.path.join(OUTPUT_DIR, output_filename)

        # Check if both source files exist before attempting to merge
        if os.path.exists(prompt_path) and os.path.exists(article_path):
            try:
                # Read prompt content
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompt_data = f.read()

                # Read article content
                with open(article_path, 'r', encoding='utf-8') as f:
                    article_data = f.read()

                # Concatenate and write to new file
                # The \n\n adds a clean break between the prompt and the article text
                combined_content = f"{prompt_data}\n{article_data}"
                
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(combined_content)
                
                print(f"Successfully created: {output_filename}")

            except Exception as e:
                print(f"Error processing index {i}: {e}")
        else:
            print(f"Skipping index {i}: One or both files missing.")

if __name__ == "__main__":
    process_sequential_files()