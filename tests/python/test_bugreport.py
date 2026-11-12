import socket
import tarfile

from quantseq_counts import bugreport


def make_run(tmp_path):
    out = tmp_path / "srv" / "alice" / "study7" / "out"; rd = out / "run"; rd.mkdir(parents=True)
    (rd / "samples.csv").write_text("sample,fastq,group\nPT0042,PT0042_R1.fastq.gz,case\nPT0099,PT0099_R1.fastq.gz,ctrl\n")
    (rd / "settings.yaml").write_text(f"run_name: 'study7'\nfastq_dir: '{tmp_path}/srv/alice/fq'\noutdir: '{out}'\n")
    (rd / "versions.tsv").write_text("process\ttool\tversion\nSTAR_ALIGN\tstar\t2.7.11b\n")
    work = out / "work" / "ab" / "cdef"; work.mkdir(parents=True)
    (work / ".command.err").write_text(f"EXITING because of fatal ERROR in reads input: PT0099 at {work}/x.fq on {socket.gethostname()}\n")
    (work / ".command.sh").write_text(f"STAR --readFilesIn {work}/PT0099_trimmed.fq.gz\n")
    (rd / "trace.txt").write_text("task_id\thash\tname\tstatus\texit\tcontainer\tcpus\tmemory\trealtime\t%cpu\tpeak_rss\tworkdir\n"
                                  f"1\tab/cdef\tSTAR_ALIGN (PT0099)\tFAILED\t102\tc.io/star:1\t8\t32 GB\t1s\t1%\t1 MB\t{work}\n")
    (rd / "nextflow.log").write_text(f"ERROR ~ Error executing process > 'STAR_ALIGN (PT0099)' in {work}\n")
    return out


def test_bugreport_scrubs(tmp_path):
    out = make_run(tmp_path)
    bundle = bugreport.make_bundle(out, tmp_path / "b")
    text = ""
    with tarfile.open(bundle) as t:
        for m in t.getmembers():
            if m.isfile():
                text += t.extractfile(m).read().decode()
    for secret in ("PT0042", "PT0099", "alice", "study7", str(tmp_path), socket.gethostname()):
        assert secret not in text, secret
    assert "S02" in text and "STAR_ALIGN" in text and "2.7.11b" in text and "fatal ERROR" in text and "<path>" in text
