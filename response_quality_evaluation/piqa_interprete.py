import json

def parse_physicaliqa(file_path):
    data_list = []
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line.strip())
            data_list.append(data)
    return data_list

# Example usage
file_path = 'piqa/physicaliqa.jsonl'
# data_list = parse_physicaliqa(file_path)
# print(data_list)

def extract_questions(file_path):
    questions = []
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line.strip())
            question = {
                "role": "system",
                "content": data.get("goal", "")
            }
            questions.append(question)
    return questions

# Example usage
# questions = extract_questions(file_path)
# print(questions)

def save_goals_to_json(file_path, output_path):
    goals = []
    with open(file_path, 'r') as file:
        for line in file:
            data = json.loads(line.strip())
            goal = data.get("goal", "")
            goals.append(goal)
    
    with open(output_path, 'w') as output_file:
        json.dump(goals, output_file, indent=4)


# Example usage
output_path = 'piqa/goals.json'
#save_goals_to_json(file_path, output_path)
#print(f"Goals have been saved to {output_path}")

def save_first_five_goals_to_json(file_path, output_path):
    goals = []
    with open(file_path, 'r') as file:
        for i, line in enumerate(file):
            if i >= 5:
                break
            data = json.loads(line.strip())
            goal = data.get("goal", "")
            goals.append(goal)
    
    with open(output_path, 'w') as output_file:
        json.dump(goals, output_file, indent=4)

# Example usage
output_path_first_five = 'piqa/goals.json'
save_first_five_goals_to_json(file_path, output_path_first_five)
print(f"First five goals have been saved to {output_path_first_five}")