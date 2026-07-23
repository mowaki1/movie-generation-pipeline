import json
import zipfile
from pathlib import Path

JOBS_DIR = Path("jobs")
OUTPUT_ZIP = "all_final_stories.zip"


def find_stories():
    for story_path in sorted(JOBS_DIR.glob("story_pipeline*/final_story.json")):
        pipeline_no = story_path.parent.name.removeprefix("story_pipeline")
        data = json.loads(story_path.read_text(encoding="utf-8"))
        genre_id = data.get("genre_id")
        yield genre_id, pipeline_no, story_path


def main():
    # ジャンルごとに、pipeline_noが大きい(=新しい)ジョブを優先して採用する
    picked = {}
    unknown = []
    for genre_id, pipeline_no, story_path in find_stories():
        if genre_id is None:
            # generate_story7.pyにgenre_id記録を追加する前に生成されたジョブ
            # (t_movie_titles.idとpipeline_noの対応が保証されないため、ジャンル不明として扱う)
            unknown.append((pipeline_no, story_path))
            continue
        if genre_id not in picked or int(pipeline_no) > int(picked[genre_id][0]):
            picked[genre_id] = (pipeline_no, story_path)

    if not picked and not unknown:
        print("final_story.jsonが見つかりませんでした")
        raise SystemExit(1)

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for genre_id, (pipeline_no, story_path) in picked.items():
            zf.write(story_path, arcname=f"genre_{genre_id}_pipeline_{pipeline_no}.json")
        for pipeline_no, story_path in unknown:
            zf.write(story_path, arcname=f"unknown_genre_pipeline_{pipeline_no}.json")

    if unknown:
        print("WARNING: genre_id未記録のためジャンル不明として同梱したジョブ:")
        for pipeline_no, _ in unknown:
            print(f"  pipeline_no={pipeline_no}")

    print(f"done: {OUTPUT_ZIP} ({len(picked)} genres known, {len(unknown)} unknown)")


if __name__ == "__main__":
    main()
