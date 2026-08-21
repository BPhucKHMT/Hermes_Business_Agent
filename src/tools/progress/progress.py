"""Flow A JSON CLI; registered targets only."""
import argparse,json
def main():
 parser=argparse.ArgumentParser(); parser.add_argument('command',choices=('ingest','preview','approve','status')); parser.add_argument('--payload'); args=parser.parse_args(); print(json.dumps({'status':'accepted','command':args.command},ensure_ascii=False))
if __name__=='__main__': main()
