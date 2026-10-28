import type { Source } from "@/lib/types";

// 停止或异常时不会收到 final，回答里残留的是模型原话中的 [E3] 这种编号。
// 这些编号没有映射关系，点不了也看不懂，直接清掉。
const RAW_CITATION_RE = /[\[【]\s*[Ee]\d+(?:\s*(?:[,，、\-–—~]\s*[Ee]?\d+)*)?\s*[\]】]/g;

/**
 * 清掉未经映射的原始证据编号，并压缩因此产生的多余空白。
 */
export function stripRawCitations(text: string): string {
  return (
    text
      .replace(RAW_CITATION_RE, "")
      // 编号常夹在空格和标点之间，删掉后会出现 "结论 , 下一句" 这种残留。
      // 先把标点前空格去掉，再把标点后多余空格压成一个。
      .replace(/[ \t]+([,，。！？；：、）】])/g, "$1")
      .replace(/([（【])[ \t]+/g, "$1")
      .replace(/[ \t]{2,}/g, " ")
      .replace(/[ \t]+$/gm, "")
      .trim()
  );
}

/**
 * sources 为空说明这一轮没有任何可跳转的出处。
 */
export function hasMappedCitations(sources: Source[]): boolean {
  return sources.length > 0;
}
