import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env')

# Add backend directory to Python path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.tools.retrieval import campus_data

def run_test():
    # You can change this prompt to whatever you want to test!
    test_prompt = "What are the rules regarding SGPA and CGPA?"
    
    print(f"Searching Longterm Database for: '{test_prompt}'\n")
    print("-" * 50)
    
    # Run the retrieval tool
    results = campus_data.invoke(test_prompt)
    
    print(results)
    print("\n" + "-" * 50)
    print("Search Complete!")

if __name__ == "__main__":
    run_test()
