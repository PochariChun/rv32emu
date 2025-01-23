/*
 * rv32emu is freely redistributable under the MIT License. See the file
 * "LICENSE" for information on usage and redistribution of this file.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <sys/stat.h>

#if defined(_WIN32)
#include <windows.h>
#else
#include <sys/ioctl.h>
#include <unistd.h>
#endif

#include "../src/riscv.h"
#include "../src/utils.h"
#include "../src/elf.h"
#include "../src/decode.h"

typedef void (*hist_record_handler)(const rv_insn_t *);

static bool ascending_order = false;
static const char *elf_prog = NULL;
static const char *out_json = NULL;
static const char *highlight_groups = NULL;

typedef struct {
    char insn_reg[16]; /* insn or reg   */
    size_t freq;       /* frequency     */
    uint8_t reg_mask;  /* 0x1=rs1, 0x2=rs2, 0x4=rs3, 0x8=rd */
} rv_hist_t;

#define N_RV_INSNS (sizeof(rv_insn_stats) / sizeof(rv_hist_t) - 1)

/* clang-format off */
static rv_hist_t rv_insn_stats[] = {
#define _(inst, can_branch, insn_len, translatable, reg_mask) {#inst, 0, reg_mask},
    RV_INSN_LIST
    _(unknown, 0, 0, 0, 0)
#undef _
};
/* clang-format on */

static void save_json_stats(const rv_hist_t *stats, size_t stats_size, const char *filename)
{
    FILE *f = fopen(filename, "w");
    if (!f) {
        fprintf(stderr, "Failed to open %s for writing\n", filename);
        return;
    }

    fprintf(f, "{\n");
    
    if (highlight_groups) {
        fprintf(f, "  \"_highlight_groups\": \"%s\",\n", highlight_groups);
    }
    
    for (size_t i = 0; i < stats_size; i++) {
        fprintf(f, "  \"%s\": {\"count\": %zu}", stats[i].insn_reg, stats[i].freq);
        if (i < stats_size - 1)
            fprintf(f, ",");
        fprintf(f, "\n");
    }
    fprintf(f, "}\n");
    fclose(f);
}

static void insn_hist_incr(const rv_insn_t *ir)
{
    if (!ir) {
        rv_insn_stats[N_RV_INSNS].freq++;
        return;
    }
    rv_insn_stats[ir->opcode].freq++;
}

#define DEFAULT_OUTPUT_DIR "build/pyvisual"

static void ensure_output_dir_exists(void) {
#if defined(_WIN32)
    mkdir(DEFAULT_OUTPUT_DIR);
#else
    mkdir(DEFAULT_OUTPUT_DIR, 0755);
#endif
}

static void print_usage(const char *filename)
{
    fprintf(stderr,
            "rv_pyvisual - RISC-V instruction frequency analyzer\n"
            "Usage: %s [-h] [-a] [-t TYPE] -i INPUT [-o OUTPUT] [-l HIGHLIGHT]\n"
            "Options:\n"
            "  -h        Show this help message\n"
            "  -a        Generate histogram in ascending order (default: descending)\n"
            "  -i INPUT  Input ELF file path\n"
            "  -o OUTPUT Output JSON file path (default: build/pyvisual/output.json)\n"
            "  -l HL     Highlight instruction groups (e.g., \"lw,lh,lb sw,sh,sb jal,jalr\")\n"
            "            Instructions in same group separated by comma\n"
            "            Different groups separated by space\n",
            filename);
}

static bool parse_args(int argc, const char *args[])
{
    bool ret = true;
    const char *input_file = NULL;
    const char *output_file = NULL;
    static char default_output[256];

    for (int i = 1; i < argc; i++) {
        const char *arg = args[i];
        if (arg[0] == '-') {
            switch (arg[1]) {
                case 'h':
                    print_usage(args[0]);
                    exit(0);
                case 'a':
                    ascending_order = true;
                    break;
                case 'i':
                    if (i + 1 < argc) {
                        input_file = args[++i];
                    } else {
                        ret = false;
                    }
                    break;
                case 'o':
                    if (i + 1 < argc) {
                        output_file = args[++i];
                    } else {
                        ret = false;
                    }
                    break;
                case 'l':
                    if (i + 1 < argc) {
                        highlight_groups = args[++i];
                    } else {
                        ret = false;
                    }
                    break;
                default:
                    ret = false;
                    break;
            }
        } else {
            ret = false;
        }
    }

    if (ret && input_file) {
        elf_prog = input_file;
        if (!output_file) {
            ensure_output_dir_exists();
            snprintf(default_output, sizeof(default_output), 
                    "%s/output.json", DEFAULT_OUTPUT_DIR);
            out_json = default_output;
        } else {
            out_json = output_file;
        }
        return true;
    }
    return false;
}

int main(int argc, const char *args[])
{
    if (!parse_args(argc, args)) {
        print_usage(args[0]);
        return 1;
    }

    elf_t *e = elf_new();
    if (!elf_open(e, elf_prog)) {
        fprintf(stderr, "Failed to open %s\n", elf_prog);
        return 1;
    }

    struct Elf32_Ehdr *hdr = get_elf_header(e);
    if (!hdr->e_shnum) {
        fprintf(stderr, "no section headers are found in %s\n", elf_prog);
        return 1;
    }

    uint8_t *elf_first_byte = get_elf_first_byte(e);
    const struct Elf32_Shdr **shdrs = 
        (const struct Elf32_Shdr **) &elf_first_byte[hdr->e_shoff];

    rv_insn_t ir;
    bool res;

    for (int i = 0; i < hdr->e_shnum; i++) {
        const struct Elf32_Shdr *shdr = (const struct Elf32_Shdr *) &shdrs[i];
        bool is_prg = shdr->sh_type & SHT_PROGBITS;
        bool has_insn = shdr->sh_flags & SHF_EXECINSTR;

        if (!(is_prg && has_insn))
            continue;

        uint8_t *exec_start_addr = &elf_first_byte[shdr->sh_offset];
        const uint8_t *exec_end_addr = &exec_start_addr[shdr->sh_size];
        uint8_t *ptr = exec_start_addr;
        uint32_t insn;

        while (ptr < exec_end_addr) {
#ifdef RV32_HAVE_EXT_C
            if ((*((uint32_t *) ptr) & FC_OPCODE) != 0x3) {
                insn = *((uint16_t *) ptr);
                ptr += 2;
                goto decode;
            }
#endif
            insn = *((uint32_t *) ptr);
            ptr += 4;

#ifdef RV32_HAVE_EXT_C
        decode:
#endif
            res = rv_decode(&ir, insn);

            if (!res) {
                insn_hist_incr(NULL);
                continue;
            }
            insn_hist_incr(&ir);
        }
    }

    save_json_stats(rv_insn_stats, N_RV_INSNS + 1, out_json);

    printf("Statistics saved to %s\n", out_json);
    printf("To generate visualization:\n");
    printf("1. Install required Python packages:\n");
    printf("   pip3 install -r tools/pyvisual/requirements.txt\n\n");
    printf("2. Run the visualization script:\n");
    printf("   python3 -m tools.pyvisual.run_analysis -i %s\n", out_json);

    elf_delete(e);
    return 0;
} 