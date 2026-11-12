// Ensembl 115 human genome (primary assembly) and annotation, downloaded once into reference_dir and checked against
// the release's CHECKSUMS files. Runs on the machine that starts the run (no container, no queue), since compute
// nodes often have no internet access.
process DOWNLOAD_REFERENCE {
    executor 'local'
    storeDir "${params.reference_dir}/ensembl_115/download"

    output:
    path 'Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz', emit: fasta
    path 'Homo_sapiens.GRCh38.115.gtf.gz',                 emit: gtf

    script:
    def base = 'https://ftp.ensembl.org/pub/release-115'
    """
    curl -fsSL --retry 3 -o CHECKSUMS.dna ${base}/fasta/homo_sapiens/dna/CHECKSUMS
    curl -fsSL --retry 3 -o CHECKSUMS.gtf ${base}/gtf/homo_sapiens/CHECKSUMS
    curl -fsSL --retry 3 -O ${base}/fasta/homo_sapiens/dna/Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz
    curl -fsSL --retry 3 -O ${base}/gtf/homo_sapiens/Homo_sapiens.GRCh38.115.gtf.gz
    check_ensembl_sum.sh CHECKSUMS.dna Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz
    check_ensembl_sum.sh CHECKSUMS.gtf Homo_sapiens.GRCh38.115.gtf.gz
    """

    stub:
    """
    touch Homo_sapiens.GRCh38.dna.primary_assembly.fa.gz Homo_sapiens.GRCh38.115.gtf.gz
    """
}
