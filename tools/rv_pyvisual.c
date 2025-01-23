/*
 * rv32emu is freely redistributable under the MIT License. See the file
 * "LICENSE" for information on usage and redistribution of this file.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

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

// 将统计数据保存为 JSON 格式
static void save_json_stats(const rv_hist_t *stats, size_t stats_size, const char *filename)
{
    FILE *f = fopen(filename, "w");
    if (!f) {
        fprintf(stderr, "Failed to open %s for writing\n", filename);
        return;
    }

    fprintf(f, "{\n");
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

static void print_usage(const char *filename)
{
    fprintf(stderr,
            "rv_pyvisual loads an ELF file to execute and generate visualization.\n"
            "Usage: %s [option] [elf_file_path] [output_json_path]\n"
            "available options: -a, generate the histogram in "
            "ascending order(default is on descending order)\n",
            filename);
}

static bool parse_args(int argc, const char *args[])
{
    bool ret = true;
    for (int i = 1; (i < argc) && ret; i++) {
        const char *arg = args[i];
        if (arg[0] == '-') {
            if (!strcmp(arg, "-a")) {
                ascending_order = true;
                continue;
            }
            ret = false;
        } else if (!elf_prog) {
            elf_prog = arg;
        } else if (!out_json) {
            out_json = arg;
        }
    }

    return ret;
}

int main(int argc, const char *args[])
{
    if (!parse_args(argc, args) || !elf_prog || !out_json) {
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

    // 保存统计数据为 JSON
    save_json_stats(rv_insn_stats, N_RV_INSNS + 1, out_json);

    // 打印提示信息
    printf("Statistics saved to %s\n", out_json);
    printf("To generate visualization, run:\n");
    char cmd[1024];
    snprintf(cmd, sizeof(cmd), "python3 -m tools.pyvisual.run_analysis -i %s", out_json);
    system(cmd);

    elf_delete(e);
    return 0;
} 