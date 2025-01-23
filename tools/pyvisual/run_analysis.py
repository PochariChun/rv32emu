#!/usr/bin/env python3
import json
import argparse
import sys
import os

try:
    import matplotlib.pyplot as plt
    import seaborn as sns
    import pandas as pd
    import numpy as np
except ImportError as e:
    print(f"Error: Missing required package - {str(e)}")
    print("\nPlease install required packages using:")
    print("pip3 install -r tools/pyvisual/requirements.txt")
    sys.exit(1)

DEFAULT_OUTPUT_DIR = "build/pyvisual"

def ensure_output_dir_exists():
    if not os.path.exists(DEFAULT_OUTPUT_DIR):
        os.makedirs(DEFAULT_OUTPUT_DIR)

def load_json_data(json_file):
    with open(json_file, 'r') as f:
        return json.load(f)

def prepare_data(data):
    # 提取指令和频率
    instructions = list(data.keys())
    frequencies = [data[inst]['count'] for inst in instructions]
    
    # 只显示频率不为0的指令
    non_zero = [(i, f) for i, f in zip(instructions, frequencies) if f > 0]
    if non_zero:
        instructions, frequencies = zip(*non_zero)
    else:
        return [], []
    
    return instructions, frequencies

def create_bar_chart(data, output_file=None):
    if output_file is None:
        ensure_output_dir_exists()
        output_file = f"{DEFAULT_OUTPUT_DIR}/instruction_bar.png"
    instructions, frequencies = prepare_data(data)
    if not instructions:
        return
    
    plt.figure(figsize=(15, 8))
    plt.bar(range(len(instructions)), frequencies)
    plt.xticks(range(len(instructions)), instructions, rotation=45, ha='right')
    
    plt.title('RISC-V Instruction Frequency (Bar Chart)')
    plt.xlabel('Instructions')
    plt.ylabel('Frequency')
    
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f"Bar chart saved as '{output_file}'")

def create_pie_chart(data, output_file=None):
    if output_file is None:
        ensure_output_dir_exists()
        output_file = f"{DEFAULT_OUTPUT_DIR}/instruction_pie.png"
    instructions, frequencies = prepare_data(data)
    if not instructions:
        return
    
    plt.figure(figsize=(12, 8))
    plt.pie(frequencies, labels=instructions, autopct='%1.1f%%')
    plt.title('RISC-V Instruction Distribution (Pie Chart)')
    
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f"Pie chart saved as '{output_file}'")

def create_heatmap(data, output_file=None):
    if output_file is None:
        ensure_output_dir_exists()
        output_file = f"{DEFAULT_OUTPUT_DIR}/instruction_heat.png"
    instructions, frequencies = prepare_data(data)
    if not instructions:
        return
    
    # 创建方形热力图
    size = int(np.ceil(np.sqrt(len(instructions))))
    heatmap_data = np.zeros((size, size))
    
    for i, freq in enumerate(frequencies):
        row = i // size
        col = i % size
        heatmap_data[row][col] = freq
    
    plt.figure(figsize=(12, 10))
    sns.heatmap(heatmap_data, annot=True, fmt='.0f', cmap='YlOrRd')
    plt.title('RISC-V Instruction Frequency (Heatmap)')
    
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f"Heatmap saved as '{output_file}'")

def create_horizontal_bar(data, output_file=None):
    if output_file is None:
        ensure_output_dir_exists()
        output_file = f"{DEFAULT_OUTPUT_DIR}/instruction_hbar.png"
    instructions, frequencies = prepare_data(data)
    if not instructions:
        return
    
    plt.figure(figsize=(10, max(8, len(instructions)*0.3)))
    y_pos = range(len(instructions))
    plt.barh(y_pos, frequencies)
    plt.yticks(y_pos, instructions)
    
    plt.title('RISC-V Instruction Frequency (Horizontal Bar)')
    plt.xlabel('Frequency')
    
    plt.tight_layout()
    plt.savefig(output_file)
    plt.close()
    print(f"Horizontal bar chart saved as '{output_file}'")

def main():
    parser = argparse.ArgumentParser(description='Visualize RISC-V instruction frequency')
    parser.add_argument('-i', '--input', required=True, help='Input JSON file')
    parser.add_argument('-t', '--type', choices=['all', 'bar', 'pie', 'heat', 'hbar'],
                      default='all', help='Type of visualization to generate')
    args = parser.parse_args()
    
    data = load_json_data(args.input)
    
    if args.type == 'all':
        create_bar_chart(data)
        create_pie_chart(data)
        create_heatmap(data)
        create_horizontal_bar(data)
    elif args.type == 'bar':
        create_bar_chart(data)
    elif args.type == 'pie':
        create_pie_chart(data)
    elif args.type == 'heat':
        create_heatmap(data)
    elif args.type == 'hbar':
        create_horizontal_bar(data)

if __name__ == '__main__':
    main() 