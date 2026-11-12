// counts.tsv, counts.rds, README.txt and excluded.tsv from the featureCounts table (workflow/bin/build_outputs.R).
process BUILD_OUTPUTS {
    label 'process_single'
    container 'biocontainers/bioconductor-summarizedexperiment:1.32.0--r43hdfd78af_0'
    publishDir "${params.outdir}", mode: 'copy'

    input:
    path counts
    path gtf
    path samples, stageAs: 'samples.csv'
    val excluded

    output:
    path 'counts.tsv',   emit: tsv
    path 'counts.rds',   emit: rds
    path 'README.txt',   emit: readme
    path 'excluded.tsv', emit: excluded

    script:
    def ex = excluded.collect { it.replace("'", "") }.join('\n')
    """
    printf '%s' '${ex}' > excluded_in.tsv
    [ -s excluded_in.tsv ] && echo >> excluded_in.tsv
    build_outputs.R --fc ${counts} --gtf ${gtf} --samples samples.csv --excluded excluded_in.tsv --version ${params.package_version} --out .
    """

    stub:
    """
    touch counts.tsv counts.rds README.txt excluded.tsv
    """
}
