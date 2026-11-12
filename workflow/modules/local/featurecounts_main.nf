// The main counts: one featureCounts call over every library, on the deduplicated alignments (UMI mode) or the
// sorted alignments (no-UMI mode): -s 1 -t exon -g gene_id, unique alignments only (no -M), a read overlapping two
// genes not counted (no -O). Each BAM is linked as <library>.bam so that the columns carry the library names.
process FEATURECOUNTS_MAIN {
    label 'process_medium'
    container 'biocontainers/subread:2.0.6--he4a0461_2'

    input:
    val ids
    path bams, stageAs: 'in/*'
    path gtf

    output:
    path 'featurecounts.txt',         emit: counts
    path 'featurecounts.txt.summary', emit: summary
    tuple val("${task.process}"), val('subread'), eval("featureCounts -v 2>&1 | sed 's/featureCounts v//' | tr -d '\\n '"), emit: versions_subread, topic: versions

    script:
    def strand = [forward: 1, reverse: 2, unstranded: 0][params.strand]
    def multi  = params.count_multimappers ? '-M' : ''
    def links  = [ids, bams instanceof List ? bams : [bams]].transpose().collect { id, b -> "ln -s ${b} ${id}.bam" }.join('\n')
    """
    ${links}
    featureCounts -s ${strand} -t exon -g gene_id ${multi} -T ${task.cpus} -a ${gtf} -o featurecounts.txt ${ids.collect { "${it}.bam" }.join(' ')}
    """

    stub:
    """
    printf '# stub\\nGeneid\\tChr\\tStart\\tEnd\\tStrand\\tLength\\t%s\\n' "${ids.collect { "${it}.bam" }.join('\\t')}" > featurecounts.txt
    echo "featureCounts -s 1 -t exon -g gene_id (stub)" >> featurecounts.txt
    touch featurecounts.txt.summary
    """
}
