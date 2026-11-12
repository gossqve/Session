"""Extended reproducible S3 invariant testing, not an algorithm experiment."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from random_serving import run_cases, settings


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seed',type=int);parser.add_argument('--cases',type=int)
    parser.add_argument('--case-index',type=int);parser.add_argument('--out',type=Path)
    args=parser.parse_args();default_seed,default_count=settings(500)
    seed=args.seed if args.seed is not None else default_seed
    count=args.cases if args.cases is not None else default_count
    if count<1 or args.case_index is not None and args.case_index<0:parser.error('positive cases/nonnegative case index required')
    if args.out:args.out.mkdir(parents=True,exist_ok=False)
    result=run_cases(seed,count,indices=[args.case_index] if args.case_index is not None else None)
    if args.out:(args.out/'summary.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(random_summary={k:v for k,v in result.items() if k!='cases'})))


if __name__=='__main__':main()
