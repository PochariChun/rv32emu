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
        data = json.load(f)
    
    highlight_groups = {}
    if '_highlight_groups' in data:
        hl_str = data['_highlight_groups']
        groups = hl_str.split()
        for i, group in enumerate(groups):
            insts = group.split(',')
            if i == 0:
                highlight_groups['Memory'] = insts
            elif i == 1:
                highlight_groups['Branch'] = insts
            elif i == 2:
                highlight_groups['Jump'] = insts
    
    if not highlight_groups:
        highlight_groups = {
            'Memory': ['lw','lh','lb','lhu','lbu','sw','sh','sb'],
            'Branch': ['bne','beq','blt','bge','bgeu','bltu'],
            'Jump': ['jal','jalr']
        }
    
    data['_highlight_groups'] = highlight_groups
    return data

def prepare_data(data):
    instructions = [key for key in data.keys() if not key.startswith('_')]
    frequencies = []
    
    for inst in instructions:
        if isinstance(data[inst], dict) and 'count' in data[inst]:
            frequencies.append(data[inst]['count'])
        else:
            frequencies.append(data[inst])
    
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
    
    total_instructions = sum(frequencies)
    
    sorted_data = sorted(zip(instructions, frequencies), 
                        key=lambda x: x[1], 
                        reverse=True)
    instructions, frequencies = zip(*sorted_data)
    
    plt.figure(figsize=(15, 8))
    bars = plt.bar(range(len(instructions)), frequencies)
    plt.xticks(range(len(instructions)), instructions, rotation=45, ha='right')
    
    for bar in bars:
        height = bar.get_height()
        percentage = (height / total_instructions) * 100
        plt.text(bar.get_x() + bar.get_width()/2, height,
                f'{int(height)}\n({percentage:.1f}%)',
                ha='center', va='bottom')
    
    plt.title(f'Execution profile for\nInstructions profiled: {total_instructions}')
    plt.xlabel('Instructions')
    plt.ylabel('Frequency')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
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
    
    total_instructions = sum(frequencies)
    
    sorted_data = sorted(zip(instructions, frequencies), 
                        key=lambda x: x[1], 
                        reverse=True)
    instructions, frequencies = zip(*sorted_data)
    
    highlight_groups = data.get('_highlight_groups', {
        'Memory': ['lw','lh','lb','lhu','lbu','sw','sh','sb'],
        'Branch': ['bne','beq','blt','bge','bgeu','bltu'],
        'Jump': ['jal','jalr']
    })
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, max(8, len(instructions)*0.3)),
                                   height_ratios=[len(instructions), 3],
                                   gridspec_kw={'hspace': 0.3})
    
    colors = ['#649ac9'] * len(instructions)  # 默认蓝色
    highlight_colors = ['#3ECCBB', '#EED595', '#f4a261']
    
    for i, inst in enumerate(instructions):
        for group_idx, (_, group_insts) in enumerate(highlight_groups.items()):
            if inst in group_insts:
                colors[i] = highlight_colors[group_idx]
                break
    
    bars = ax1.barh(range(len(instructions)), frequencies, color=colors)
    ax1.set_yticks(range(len(instructions)))
    ax1.set_yticklabels(instructions)
    
    for i, bar in enumerate(bars):
        width = bar.get_width()
        percentage = (width / total_instructions) * 100
        ax1.text(width + (total_instructions * 0.01),
                bar.get_y() + bar.get_height()/2,
                f'{int(width)} ({percentage:.1f}%)',
                va='center')
    
    type_stats = {
        'ARITH': 0,
        'MEM': 0,
        'BRANCH': 0
    }
    
    for inst, freq in zip(instructions, frequencies):
        if inst in highlight_groups['Memory']:
            type_stats['MEM'] += freq
        elif inst in highlight_groups['Branch']:
            type_stats['BRANCH'] += freq
        elif inst in highlight_groups['Jump']:
            type_stats['BRANCH'] += freq
        else:
            type_stats['ARITH'] += freq
    
    type_bars = ax2.barh(range(len(type_stats)), list(type_stats.values()),
                         color=['#649ac9', '#3ECCBB', '#EED595'])
    ax2.set_yticks(range(len(type_stats)))
    ax2.set_yticklabels(type_stats.keys())
    
    for bar in type_bars:
        width = bar.get_width()
        percentage = (width / total_instructions) * 100
        ax2.text(width + (total_instructions * 0.01),
                bar.get_y() + bar.get_height()/2,
                f'{int(width)} ({percentage:.1f}%)',
                va='center')
    
    fig.suptitle(f'Execution profile for\nInstructions profiled: {total_instructions}')
    ax1.set_xlabel('Count')
    ax2.set_xlabel('Count')
    
    for i, (group_name, _) in enumerate(highlight_groups.items()):
        ax1.barh([], [], color=highlight_colors[i], label=group_name)
    ax1.legend(loc='lower right', title='Instruction Types')
    
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
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