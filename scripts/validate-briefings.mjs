import { readFile } from 'node:fs/promises';

const archive = JSON.parse(await readFile(new URL('../data/briefings.json', import.meta.url), 'utf8'));
const checkLinks = process.argv.includes('--check-links');
const errors = [];
const warnings = [];

const normalizeText = (value) => String(value ?? '')
  .toLocaleLowerCase('ko-KR')
  .replace(/[^0-9a-z가-힣]+/g, ' ')
  .trim();

function canonicalURL(value) {
  if (!value) return '';
  try {
    const url = new URL(value);
    if (!['http:', 'https:'].includes(url.protocol)) return '';
    ['utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content', 'fbclid', 'gclid']
      .forEach(key => url.searchParams.delete(key));
    url.hash = '';
    url.pathname = url.pathname.replace(/\/$/, '') || '/';
    return url.href;
  } catch {
    return '';
  }
}

function titleGrams(value) {
  const text = normalizeText(value).replaceAll(' ', '');
  const grams = new Set();
  for (let index = 0; index < Math.max(1, text.length - 2); index += 1) {
    grams.add(text.slice(index, index + 3));
  }
  return grams;
}

function titleSimilarity(left, right) {
  const a = titleGrams(left);
  const b = titleGrams(right);
  if (!a.size || !b.size) return 0;
  const overlap = [...a].filter(value => b.has(value)).length;
  return (2 * overlap) / (a.size + b.size);
}

if (!Array.isArray(archive) || !archive.length) errors.push('브리핑 배열이 비어 있습니다.');

const articles = archive.flatMap(brief => {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(brief.date ?? '')) errors.push(`잘못된 브리핑 날짜: ${brief.date}`);
  if (!Array.isArray(brief.executiveSummary) || brief.executiveSummary.length < 2 || brief.executiveSummary.length > 3) {
    errors.push(`${brief.date}: executiveSummary는 2~3개 문장이어야 합니다.`);
  }
  return (brief.news ?? []).map(article => ({ ...article, briefingDate: brief.date }));
});

const requiredFields = ['id', 'title', 'summary', 'insight', 'whyItMatters', 'recommendedAction', 'source', 'sourceType', 'published', 'region'];
const ids = new Set();

for (const article of articles) {
  for (const field of requiredFields) {
    if (!article[field]) errors.push(`${article.id || article.title || '알 수 없는 기사'}: ${field} 누락`);
  }
  if (ids.has(article.id)) errors.push(`${article.id}: 중복 ID`);
  ids.add(article.id);
  if (article.url && !canonicalURL(article.url)) errors.push(`${article.id}: 올바르지 않은 원문 URL`);
  if (!article.url) warnings.push(`${article.id}: 기존 기사에 검증된 원문 URL이 없습니다.`);
}

for (let index = 0; index < articles.length; index += 1) {
  for (let compare = index + 1; compare < articles.length; compare += 1) {
    const left = articles[index];
    const right = articles[compare];
    if (left.relatedTo === right.id || right.relatedTo === left.id) continue;
    const sameURL = canonicalURL(left.url) && canonicalURL(left.url) === canonicalURL(right.url);
    const similarity = titleSimilarity(left.title, right.title);
    if (sameURL || similarity >= .88) {
      errors.push(`${left.id} ↔ ${right.id}: ${sameURL ? '동일 URL' : `유사 제목 ${Math.round(similarity * 100)}%`}`);
    }
  }
}

async function verifyLink(article) {
  if (!article.url) return;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(article.url, {
      method: 'GET',
      redirect: 'follow',
      signal: controller.signal,
      headers: {
        'user-agent': 'Mozilla/5.0 (compatible; ConstructionBriefLinkCheck/1.0)',
        range: 'bytes=0-1024'
      }
    });
    if ([404, 410].includes(response.status)) {
      errors.push(`${article.id}: 원문 링크가 끊어졌습니다. (HTTP ${response.status})`);
    } else if (response.status >= 400 && ![401, 403, 405, 429].includes(response.status)) {
      warnings.push(`${article.id}: 원문 확인이 필요합니다. (HTTP ${response.status})`);
    }
  } catch (error) {
    warnings.push(`${article.id}: 네트워크에서 원문을 확인하지 못했습니다. (${error.name})`);
  } finally {
    clearTimeout(timer);
  }
}

if (checkLinks) await Promise.all(articles.map(verifyLink));

warnings.forEach(message => console.warn(`경고: ${message}`));
errors.forEach(message => console.error(`오류: ${message}`));

if (errors.length) {
  console.error(`검사 실패: 오류 ${errors.length}건, 경고 ${warnings.length}건`);
  process.exit(1);
}

console.log(`검사 완료: 브리핑 ${archive.length}개, 기사 ${articles.length}건, 경고 ${warnings.length}건`);
