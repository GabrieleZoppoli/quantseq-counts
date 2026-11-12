#!/usr/bin/env nextflow
// quantseq-counts: QuantSeq 3' mRNA-Seq FWD FASTQ to gene counts, QC and a record of the run.
// Started by `quantseq-counts run`, which writes run/settings.yaml (-params-file) and run/run.config (-c).

include { DOWNLOAD_REFERENCE          } from './modules/local/download_reference'
include { SORT_NAME_THEN_POSITION     } from './modules/local/sort_name_then_position'
include { STORE_REFERENCE             } from './modules/local/store_reference'
include { FEATURECOUNTS_MAIN          } from './modules/local/featurecounts_main'
include { BUILD_OUTPUTS               } from './modules/local/build_outputs'
include { QUANTSEQ_SCREEN             } from './modules/local/quantseq_screen'
include { QC_TABLE                    } from './modules/local/qc_table'
include { DEDUP_POSITION              } from './modules/local/dedup_position'
include { MULTIQC                     } from './modules/nf-core/multiqc/main'
include { GUNZIP as GUNZIP_FASTA      } from './modules/nf-core/gunzip/main'
include { GUNZIP as GUNZIP_GTF        } from './modules/nf-core/gunzip/main'
include { CUSTOM_GTFFILTER            } from './modules/nf-core/custom/gtffilter/main'
include { EAUTILS_GTF2BED             } from './modules/nf-core/ea-utils/gtf2bed/main'
include { STAR_GENOMEGENERATE         } from './modules/nf-core/star/genomegenerate/main'
include { FQ_LINT                     } from './modules/nf-core/fq/lint/main'
include { FQ_LINT as FQ_LINT_AFTER_TRIMMING } from './modules/nf-core/fq/lint/main'
include { FASTQC                      } from './modules/nf-core/fastqc/main'
include { UMITOOLS_EXTRACT            } from './modules/nf-core/umitools/extract/main'
include { TRIMGALORE                  } from './modules/nf-core/trimgalore/main'
include { STAR_ALIGN                  } from './modules/nf-core/star/align/main'
include { SAMTOOLS_STATS              } from './modules/nf-core/samtools/stats/main'
include { SAMTOOLS_FLAGSTAT           } from './modules/nf-core/samtools/flagstat/main'
include { SAMTOOLS_IDXSTATS           } from './modules/nf-core/samtools/idxstats/main'
include { UMICOLLAPSE                 } from './modules/nf-core/umicollapse/main'
include { SAMTOOLS_INDEX as SAMTOOLS_INDEX_DEDUP       } from './modules/nf-core/samtools/index/main'
include { SAMTOOLS_STATS as SAMTOOLS_STATS_DEDUP       } from './modules/nf-core/samtools/stats/main'
include { SAMTOOLS_FLAGSTAT as SAMTOOLS_FLAGSTAT_DEDUP } from './modules/nf-core/samtools/flagstat/main'
include { SAMTOOLS_IDXSTATS as SAMTOOLS_IDXSTATS_DEDUP } from './modules/nf-core/samtools/idxstats/main'
include { SUBREAD_FEATURECOUNTS       } from './modules/nf-core/subread/featurecounts/main'
include { CUSTOM_MULTIQCCUSTOMBIOTYPE } from './modules/nf-core/custom/multiqccustombiotype/main'
include { SAMTOOLS_SORT as SAMTOOLS_SORT_QUALIMAP } from './modules/nf-core/samtools/sort/main'
include { QUALIMAP_RNASEQ             } from './modules/nf-core/qualimap/rnaseq/main'
include { RSEQC_BAMSTAT               } from './modules/nf-core/rseqc/bamstat/main'
include { RSEQC_INFEREXPERIMENT       } from './modules/nf-core/rseqc/inferexperiment/main'
include { RSEQC_JUNCTIONANNOTATION    } from './modules/nf-core/rseqc/junctionannotation/main'
include { RSEQC_JUNCTIONSATURATION    } from './modules/nf-core/rseqc/junctionsaturation/main'
include { RSEQC_READDISTRIBUTION      } from './modules/nf-core/rseqc/readdistribution/main'
include { RSEQC_READDUPLICATION       } from './modules/nf-core/rseqc/readduplication/main'
include { DUPRADAR                    } from './modules/nf-core/dupradar/main'

// Where the reference and its STAR index are stored, so that runs on the same reference reuse them.
def referenceId() {
    if (params.reference == 'ensembl_115') return 'ensembl_115'
    def f = file(params.fasta, checkIfExists: true); def g = file(params.gtf, checkIfExists: true)
    return 'custom_' + "${f.toAbsolutePath()}:${f.size()}:${g.toAbsolutePath()}:${g.size()}".md5().take(12)
}

// One "process<TAB>tool<TAB>version" row per tool: from a version tuple, or from an older module's versions.yml
def versionRows(v) {
    if (v instanceof List && v.size() == 3) return ["${v[0].toString().tokenize(':')[-1]}\t${v[1]}\t${v[2]}"]
    def rows = []; def proc = null
    v.toString().endsWith('.yml') && file(v.toString()).eachLine { line ->
        def p = line =~ /^"?([^\s":][^":]*(?::[^":]+)*)"?:\s*$/
        def q = line =~ /^\s+([^:]+):\s*(.*)$/
        if (p) proc = p[0][1].tokenize(':')[-1]
        else if (q && proc) rows << "${proc}\t${q[0][1].trim()}\t${q[0][2].trim().replaceAll(/^['"]|['"]$/, '')}"
    }
    return rows
}

def trimmedReads(log_file) {  // as nf-core/rnaseq 3.26.0 (fastq_fastqc_umitools_trimgalore)
    def total = 0; def filtered = 0
    log_file.eachLine { line ->
        def t = line =~ /([\d\.]+)\ssequences processed in total/
        def f = line =~ /shorter than the length cutoff[^:]+:\s*([\d\.]+)/
        if (t) total = t[0][1].toFloat()
        if (f) filtered = f[0][1].toFloat()
    }
    return total - filtered
}

// run/DONE marks a run that ended without error: `quantseq-counts run` refuses an output folder that holds one
workflow.onComplete = {
    if (workflow.success) {
        file("${params.outdir}/run/DONE").text = "quantseq-counts ${params.package_version} run ${params.run_name} ended ${workflow.complete}\n"
    }
}

workflow {
    def umi = params.library == 'fwd_umi'

    // ---- reference: prepared once and kept in reference_dir/<reference id>/ (MANIFEST written last)
    def ref = [id: referenceId()]
    def stored = file("${params.reference_dir}/${ref.id}")
    def ch_fasta; def ch_gtf; def ch_bed; def ch_index
    if (file("${stored}/MANIFEST").exists()) {
        ch_fasta = channel.value([ref, file("${stored}/genome.fa")])
        ch_gtf   = channel.value([ref, file("${stored}/genes.gtf")])
        ch_bed   = channel.value(file("${stored}/genes.bed"))
        ch_index = channel.value([ref, file("${stored}/star")])
    } else {
        def fasta_in; def gtf_in
        if (params.reference == 'ensembl_115') {
            DOWNLOAD_REFERENCE()
            fasta_in = DOWNLOAD_REFERENCE.out.fasta
            gtf_in   = DOWNLOAD_REFERENCE.out.gtf
        } else {
            fasta_in = channel.value(file(params.fasta, checkIfExists: true))
            gtf_in   = channel.value(file(params.gtf, checkIfExists: true))
        }
        GUNZIP_FASTA(fasta_in.filter { f -> f.name.endsWith('.gz') }.map { f -> [ref, f] })
        ch_fasta = GUNZIP_FASTA.out.gunzip.mix(fasta_in.filter { f -> !f.name.endsWith('.gz') }.map { f -> [ref, f] }).first()
        GUNZIP_GTF(gtf_in.filter { f -> f.name.endsWith('.gz') }.map { f -> [ref, f] })
        def gtf_raw = GUNZIP_GTF.out.gunzip.mix(gtf_in.filter { f -> !f.name.endsWith('.gz') }.map { f -> [ref, f] }).first()
        CUSTOM_GTFFILTER(gtf_raw, ch_fasta)
        ch_gtf = CUSTOM_GTFFILTER.out.gtf.first()
        EAUTILS_GTF2BED(ch_gtf)
        ch_bed = EAUTILS_GTF2BED.out.bed.map { _m, b -> b }.first()
        STAR_GENOMEGENERATE(ch_fasta, ch_gtf)
        ch_index = STAR_GENOMEGENERATE.out.index.first()
        STORE_REFERENCE(
            ch_fasta.join(ch_gtf).join(EAUTILS_GTF2BED.out.bed).join(STAR_GENOMEGENERATE.out.index),
            stored.toString())
    }

    // ---- libraries
    def ch_reads = channel.fromPath(params.samples, checkIfExists: true)
        .splitCsv(header: true, strip: true)
        .map { row -> [[id: row.sample, single_end: true, strandedness: params.strand, group: row.group ?: null],
                       file("${params.fastq_dir}/${row.fastq}", checkIfExists: true)] }
    FQ_LINT(ch_reads)
    FASTQC(ch_reads)
    QUANTSEQ_SCREEN(ch_reads)
    def ch_to_trim = ch_reads
    if (umi) {
        UMITOOLS_EXTRACT(ch_reads)
        ch_to_trim = UMITOOLS_EXTRACT.out.reads
    }
    TRIMGALORE(ch_to_trim)
    def ch_trimmed = TRIMGALORE.out.reads.join(TRIMGALORE.out.log)
        .map { meta, reads, log -> [meta, reads, trimmedReads(log)] }
    def ch_kept = ch_trimmed.filter { _m, _r, n -> n >= params.min_trimmed_reads }.map { m, r, _n -> [m, r] }
    def ch_excluded = ch_trimmed.filter { _m, _r, n -> n < params.min_trimmed_reads }
        .map { m, _r, n -> "${m.id}\tfewer than ${params.min_trimmed_reads} reads after trimming (${n as long})" }
        .toSortedList()
    FQ_LINT_AFTER_TRIMMING(ch_kept)

    // ---- alignment, the new sort, deduplication
    STAR_ALIGN(ch_kept, ch_index, ch_gtf, false)
    SORT_NAME_THEN_POSITION(STAR_ALIGN.out.bam)
    def ch_sorted = SORT_NAME_THEN_POSITION.out.bam_bai
    def no_ref = channel.value([[:], [], []])
    SAMTOOLS_STATS(ch_sorted, no_ref)
    SAMTOOLS_FLAGSTAT(ch_sorted)
    SAMTOOLS_IDXSTATS(ch_sorted)
    def ch_count = ch_sorted
    if (umi) {
        UMICOLLAPSE(ch_sorted, 'bam')
        SAMTOOLS_INDEX_DEDUP(UMICOLLAPSE.out.bam)
        ch_count = UMICOLLAPSE.out.bam.join(SAMTOOLS_INDEX_DEDUP.out.index)
        SAMTOOLS_STATS_DEDUP(ch_count, no_ref)
        SAMTOOLS_FLAGSTAT_DEDUP(ch_count)
        SAMTOOLS_IDXSTATS_DEDUP(ch_count)
    } else if (params.dedup_without_umi) {
        DEDUP_POSITION(ch_sorted)
        ch_count = DEDUP_POSITION.out.bam_bai
    }

    // ---- the main counts and the R outputs
    def ch_count_sorted = ch_count.map { m, b, _i -> [m.id, b] }.toSortedList { x, y -> x[0] <=> y[0] }
    FEATURECOUNTS_MAIN(ch_count_sorted.map { l -> l.collect { it[0] } }, ch_count_sorted.map { l -> l.collect { it[1] } },
                       ch_gtf.map { _m, g -> g })
    BUILD_OUTPUTS(FEATURECOUNTS_MAIN.out.counts, ch_gtf.map { _m, g -> g }, file(params.samples), ch_excluded)

    // ---- tool versions of every process, for run/versions.tsv
    channel.topic('versions').flatMap { v -> versionRows(v) }.unique()
        .collectFile(name: 'versions.tsv', storeDir: "${params.outdir}/run", sort: true, newLine: true, seed: "process\ttool\tversion")

    // ---- QC on the alignments that are counted
    def gtf_file = ch_gtf.map { _m, g -> g }
    SUBREAD_FEATURECOUNTS(ch_count.map { m, b, _i -> [m, b] }.combine(gtf_file))
    CUSTOM_MULTIQCCUSTOMBIOTYPE(SUBREAD_FEATURECOUNTS.out.counts, channel.value([[:], file("${projectDir}/assets/biotypes_header.txt")]))
    if (!params.skip_qualimap) {
        SAMTOOLS_SORT_QUALIMAP(ch_count.map { m, b, _i -> [m, b] }, no_ref, '')
        QUALIMAP_RNASEQ(SAMTOOLS_SORT_QUALIMAP.out.bam, ch_gtf)
    }
    if (!params.skip_rseqc) {
        RSEQC_BAMSTAT(ch_count)
        RSEQC_INFEREXPERIMENT(ch_count, ch_bed)
        RSEQC_JUNCTIONANNOTATION(ch_count, ch_bed)
        RSEQC_JUNCTIONSATURATION(ch_count, ch_bed)
        RSEQC_READDISTRIBUTION(ch_count, ch_bed)
        RSEQC_READDUPLICATION(ch_count)
    }
    if (!params.skip_dupradar) {
        DUPRADAR(ch_count.map { m, b, _i -> [m, b] }, ch_gtf)
    }

    // ---- the per-library QC table, its first page, and MultiQC over everything
    def ch_screen = QUANTSEQ_SCREEN.out.tsv.collectFile(name: 'screen.tsv', sort: true,
        seed: "library\treads\tmean_length\tumi_with_n\ttata_exact\tpolyA8_any\tadapter12_any\n")
    def ch_logs = STAR_ALIGN.out.log_final.map { _m, f -> f }
        .mix(TRIMGALORE.out.log.map { _m, f -> f })
    if (umi) ch_logs = ch_logs.mix(SAMTOOLS_FLAGSTAT_DEDUP.out.flagstat.map { _m, f -> f })
    def changes = file("${params.outdir}/run/changes.tsv").exists() ? file("${params.outdir}/run/changes.tsv") : file("${projectDir}/assets/no_changes.tsv")
    QC_TABLE(ch_logs.collect(), ch_screen, FEATURECOUNTS_MAIN.out.summary, file("${projectDir}/../schema/qc_thresholds.json"),
             changes, BUILD_OUTPUTS.out.excluded)
    def ch_mqc = channel.empty()
        .mix(QC_TABLE.out.page, FASTQC.out.zip.map { _m, f -> f }, TRIMGALORE.out.log.map { _m, f -> f },
             STAR_ALIGN.out.log_final.map { _m, f -> f }, SAMTOOLS_STATS.out.stats.map { _m, f -> f },
             SAMTOOLS_FLAGSTAT.out.flagstat.map { _m, f -> f }, SAMTOOLS_IDXSTATS.out.idxstats.map { _m, f -> f },
             FEATURECOUNTS_MAIN.out.summary, CUSTOM_MULTIQCCUSTOMBIOTYPE.out.tsv.map { _m, f -> f })
    if (umi) ch_mqc = ch_mqc.mix(UMICOLLAPSE.out.log.map { _m, f -> f }, SAMTOOLS_STATS_DEDUP.out.stats.map { _m, f -> f })
    if (!params.skip_qualimap) ch_mqc = ch_mqc.mix(QUALIMAP_RNASEQ.out.results.map { _m, f -> f })
    if (!params.skip_rseqc) ch_mqc = ch_mqc.mix(RSEQC_BAMSTAT.out.txt.map { _m, f -> f }, RSEQC_INFEREXPERIMENT.out.txt.map { _m, f -> f },
        RSEQC_READDISTRIBUTION.out.txt.map { _m, f -> f }, RSEQC_JUNCTIONANNOTATION.out.log.map { _m, f -> f })
    if (!params.skip_dupradar) ch_mqc = ch_mqc.mix(DUPRADAR.out.multiqc.map { _m, f -> f })
    MULTIQC(ch_mqc.collect().map { fs -> [[id: 'multiqc'], fs, file("${projectDir}/assets/multiqc_config.yml"), [], [], []] })
}
