"""Build a GitHub Pages snapshot without calling an LLM."""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def build(destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    for name in ('index.html', 'style.css', 'dashboard.js', 'charts.js', 'research.js'):
        shutil.copyfile(ROOT/name, destination/name)
    page = (destination/'index.html').read_text(encoding='utf-8')
    page = page.replace('data-mode="live"', 'data-mode="snapshot"')
    page = page.replace('href="/style.css"', 'href="style.css"').replace('src="/', 'src="')
    page = page.replace('검토용 저장 화면 · 실시간 자동 갱신 연결 전', '예약 수집 결과 · 시세 시각과 갱신 시각을 확인하세요')
    (destination/'index.html').write_text(page, encoding='utf-8')
    (destination/'.nojekyll').touch()
    target=destination/'data';target.mkdir(exist_ok=True)
    for name in ('latest.json','intraday.json','update-status.json','history.json'):
        shutil.copyfile(ROOT/'data'/name,target/name)
    if (ROOT/'data'/'plans.json').exists():
        shutil.copyfile(ROOT/'data'/'plans.json',target/'plans.json')
    snapshot=json.loads((target/'latest.json').read_text(encoding='utf-8'))
    charts=target/'charts';charts.mkdir(exist_ok=True)
    for row in snapshot['results']:
        if row.get('chart_id'):
            name=row['chart_id']+'.json.gz'
            shutil.copyfile(ROOT/'data'/'charts'/name,charts/name)


if __name__=='__main__':
    build(ROOT.parent/'dist')
