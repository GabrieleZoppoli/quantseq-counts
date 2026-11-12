// qc/samples.tsv and the report's first page (workflow/bin/qc_table.py), from the per-library logs.
process QC_TABLE {
    label 'process_single'
    container 'biocontainers/python:3.12.12'
    publishDir "${params.outdir}/qc", mode: 'copy', pattern: 'samples.tsv'

    input:
    path logs, stageAs: 'in/*'
    path screen, stageAs: 'in/screen.tsv'
    path summary, stageAs: 'in/featurecounts.txt.summary'
    path thresholds
    path changes, stageAs: 'changes.tsv'
    path excluded, stageAs: 'excluded.tsv'

    output:
    path 'samples.tsv',      emit: tsv
    path 'summary_mqc.html', emit: page

    script:
    """
    qc_table.py --dir in --library ${params.library} --thresholds ${thresholds} --changes changes.tsv --excluded excluded.tsv --out .
    """

    stub:
    """
    touch samples.tsv summary_mqc.html
    """
}
