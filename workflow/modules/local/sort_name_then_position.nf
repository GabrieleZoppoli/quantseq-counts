// The step added to the reference run: sort by read name, then (stably) by position, so that the order of reads tied on
// position, and hence the read UMICollapse keeps among duplicates, depends on the read names only and not on STAR's
// thread scheduling (docs/design.md). With ext.deterministic false it runs the position sort alone, as before.
process SORT_NAME_THEN_POSITION {
    tag "$meta.id"
    label 'process_medium'
    container 'community.wave.seqera.io/library/htslib_samtools:1.23.1--5b6bb4ede7e612e5'

    input:
    tuple val(meta), path(bam)

    output:
    tuple val(meta), path("${meta.id}.sorted.bam"), path("${meta.id}.sorted.bam.bai"), emit: bam_bai
    tuple val("${task.process}"), val('samtools'), eval("samtools --version | sed -n '1s/samtools //p'"), emit: versions_samtools, topic: versions

    script:
    def deterministic = task.ext.deterministic == null ? true : task.ext.deterministic
    def threads = task.cpus > 1 ? "-@ ${task.cpus - 1}" : ''
    if (deterministic)
        """
        samtools sort -n --no-PG ${threads} -T ${meta.id}.byname -o ${meta.id}.byname.bam ${bam}
        samtools sort --no-PG ${threads} -T ${meta.id}.sorted -o ${meta.id}.sorted.bam ${meta.id}.byname.bam
        rm ${meta.id}.byname.bam
        samtools index ${threads} ${meta.id}.sorted.bam
        """
    else
        """
        samtools sort --no-PG ${threads} -T ${meta.id}.sorted -o ${meta.id}.sorted.bam ${bam}
        samtools index ${threads} ${meta.id}.sorted.bam
        """

    stub:
    """
    echo "samtools sort -n --no-PG / samtools sort --no-PG (stub)" > ${meta.id}.sorted.bam
    touch ${meta.id}.sorted.bam.bai
    """
}
