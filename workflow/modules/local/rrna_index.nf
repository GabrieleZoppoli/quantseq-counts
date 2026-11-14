// Once per run: a STAR index of the human 45S pre-rRNA region (workflow/assets/rdna_45s.fa, GenBank U13369.1 bases
// 1-13,314) and a BED of the mitochondrial rRNA genes of the run's GTF (gene_biotype Mt_rRNA; empty if none).
process RRNA_INDEX {
    label 'process_single'
    container 'community.wave.seqera.io/library/htslib_samtools_star_gawk:ae438e9a604351a4'

    input:
    path fasta
    path gtf

    output:
    path 'rdna_index',   emit: index
    path 'mt_rrna.bed',  emit: mt_bed
    tuple val("${task.process}"), val('star'), eval('STAR --version | sed "s/STAR_//"'), emit: versions_star, topic: versions

    script:
    """
    mkdir rdna_index
    STAR --runMode genomeGenerate --genomeDir rdna_index --genomeFastaFiles ${fasta} --genomeSAindexNbases 5 \\
        --runThreadN 1 --outFileNamePrefix rdna_index/
    gawk -F'\\t' -v OFS='\\t' '\$3 == "exon" && \$9 ~ /gene_biotype "Mt_rRNA"/ {print \$1, \$4 - 1, \$5}' ${gtf} > mt_rrna.bed
    """

    stub:
    """
    mkdir rdna_index; touch mt_rrna.bed
    """
}
