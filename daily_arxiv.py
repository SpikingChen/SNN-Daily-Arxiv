import datetime
import random
import time
import requests
import json
import arxiv
import os

base_url = "https://arxiv.paperswithcode.com/api/v0/papers/"

# arXiv 按来源 IP 限流，官方要求 1 请求 / 3 秒；GitHub Actions 是共享出口 IP，
# 被连带限流是常态，因此这些状态码值得退避重试
RETRY_STATUS = {429, 500, 502, 503, 504}
MAX_FETCH_ATTEMPTS = 6


def get_authors(authors, first_author = False):
    output = str()
    if first_author == False:
        output = ", ".join(str(author) for author in authors)
    else:
        output = authors[0]
    return output


def sort_papers(papers):
    output = dict()
    keys = list(papers.keys())
    keys.sort(reverse=True)
    for key in keys:
        output[key] = papers[key]
    return output


def fetch_results(client, search_engine, max_attempts = MAX_FETCH_ATTEMPTS):
    """
    抓取完整结果集，遇到限流按指数退避重试。
    失败后从已拿到的条数续抓，不从头再来。
    @return list[arxiv.Result]
    """
    results = []
    for attempt in range(max_attempts):
        try:
            for result in client.results(search_engine, offset = len(results)):
                results.append(result)
            return results
        except arxiv.UnexpectedEmptyPageError:
            # 翻到空页，说明结果已经取完
            return results
        except arxiv.ArxivError as e:
            status = getattr(e, "status", None)
            if status not in RETRY_STATUS or attempt == max_attempts - 1:
                raise
            # 5/10/20/40/60 秒，加抖动避免多个 job 同时解开封印又同时打过去
            wait = min(60.0, 5.0 * (2 ** attempt)) + random.uniform(0, 3)
            print(f"[retry] HTTP {status}, 已有 {len(results)} 条, "
                  f"{attempt + 1}/{max_attempts}, 等待 {wait:.1f}s")
            time.sleep(wait)
    return results


def get_daily_papers(topic, query="SNN", max_results=2):
    """
    @param topic: str
    @param query: str
    @return paper_with_code: dict
    """

    # output
    content = dict()
    content_to_web = dict()

    # content
    output = dict()

    # page_size 与 max_results 对齐，一页拿完，减少请求数（arXiv 单页上限 2000）
    client = arxiv.Client(page_size=200, delay_seconds=3.0, num_retries=3)

    search_engine = arxiv.Search(
        query = query,
        max_results = max_results,
        sort_by = arxiv.SortCriterion.SubmittedDate
    )

    cnt = 0

    # 单次抓取失败不再中断整个流程，用已有 json 重新生成 README 即可
    try:
        results = fetch_results(client, search_engine)
    except Exception as e:
        print(f"[warn] topic '{topic}' 抓取失败，跳过本次: {e!r}")
        results = []

    for result in results:

        paper_id            = result.get_short_id()
        paper_title         = result.title
        paper_url           = result.entry_id
        code_url            = base_url + paper_id
        paper_abstract      = result.summary.replace("\n"," ")
        paper_authors       = get_authors(result.authors)
        paper_first_author  = get_authors(result.authors,first_author = True)
        primary_category    = result.primary_category
        publish_time        = result.published.date()
        update_time         = result.updated.date()
        comments            = result.comment

        print("Time = ", update_time ,
              " title = ", paper_title,
              " author = ", paper_first_author)

        # eg: 2108.09112v1 -> 2108.09112
        ver_pos = paper_id.find('v')
        if ver_pos == -1:
            paper_key = paper_id
        else:
            paper_key = paper_id[0:ver_pos]

        try:
            cnt += 1
            repo_url = paper_url
            content[paper_key] = f"|**{update_time}**|**{paper_title}**|{paper_first_author} et.al.|[{paper_id}]({paper_url})|**[link]({repo_url})**|\n"
            content_to_web[paper_key] = f"- {update_time}, **{paper_title}**, {paper_first_author} et.al., Paper: [{paper_url}]({paper_url})"


            # TODO: select useful comments
            if comments != None:
                content_to_web[paper_key] = content_to_web[paper_key] + f", {comments}\n"
            else:
                content_to_web[paper_key] = content_to_web[paper_key] + f"\n"

        except Exception as e:
            print(f"exception: {e} with id: {paper_key}")

    sorted_content = dict(sorted(content.items(), key=lambda x: x[1].split('|')[1], reverse=True))
    sorted_content_to_web = dict(sorted(content_to_web.items(), key=lambda x: x[1].split(',')[0], reverse=True))

    data = {topic:sorted_content}
    data_web = {topic:sorted_content_to_web}
    return data, data_web


def update_json_file(filename, data_all):
    with open(filename,"r") as f:
        content = f.read()
        if not content:
            m = {}
        else:
            m = json.loads(content)

    json_data = m.copy()

    # update papers in each keywords
    for data in data_all:
        for keyword in data.keys():
            papers = data[keyword]

            if keyword in json_data.keys():
                json_data[keyword].update(papers)
            else:
                json_data[keyword] = papers

    for keyword in json_data.keys():
        papers = json_data[keyword]
        sorted_papers = dict(sorted(papers.items(), key=lambda x: x[1].split('|')[1], reverse=True))
        json_data[keyword] = sorted_papers

    with open(filename, "w") as f:
        json.dump(json_data, f)


def json_to_md(filename, md_filename,
               to_web = False,
               use_title = True,
               use_tc = True,
               show_badge = False):
    """
    @param filename: str
    @param md_filename: str
    @return None
    """

    DateNow = datetime.date.today()
    DateNow = str(DateNow)
    DateNow = DateNow.replace('-','.')

    with open(filename,"r") as f:
        content = f.read()
        if not content:
            data = {}
        else:
            data = json.loads(content)

    # clean README.md if daily already exist else create it
    with open(md_filename,"w+") as f:
        pass

    # write data into README.md
    with open(md_filename,"a+") as f:

        if (use_title == True) and (to_web == True):
            f.write("---\n" + "layout: default\n" + "---\n\n")

        if show_badge == True:
            f.write(f"[![Contributors][contributors-shield]][contributors-url]\n")
            f.write(f"[![Forks][forks-shield]][forks-url]\n")
            f.write(f"[![Stargazers][stars-shield]][stars-url]\n")
            f.write(f"[![Issues][issues-shield]][issues-url]\n\n")

        if use_title == True:
            f.write("## Updated on " + DateNow + "\n\n")
        else:
            f.write("> Updated on " + DateNow + "\n\n")

        #Add: table of contents
        if use_tc == True:
            f.write("<details>\n")
            f.write("  <summary>Table of Contents</summary>\n")
            f.write("  <ol>\n")
            for keyword in data.keys():
                day_content = data[keyword]
                if not day_content:
                    continue
                kw = keyword.replace(' ','-')
                f.write(f"    <li><a href=#{kw}>{keyword}</a></li>\n")
            f.write("  </ol>\n")
            f.write("</details>\n\n")

        for keyword in data.keys():
            day_content = data[keyword]
            if not day_content:
                continue
            # the head of each part
            f.write(f"## {keyword}\n\n")

            if use_title == True :
                if to_web == False:
                    f.write("|Publish Date|Title|Authors|PDF|\n" + "|---|---|---|---|\n")
                else:
                    f.write("| Publish Date | Title | Authors | PDF |\n")
                    f.write("|:---------|:-----------------------|:---------|:------|\n")

            for _,v in day_content.items():
                if v is not None:
                    f.write(v)

            f.write(f"\n")

            #Add: back to top
            top_info = f"#Updated on {DateNow}"
            top_info = top_info.replace(' ','-').replace('.','')
            f.write(f"<p align=right>(<a href={top_info}>back to top</a>)</p>\n\n")

        if show_badge == True:
            f.write(f"[contributors-shield]: https://img.shields.io/github/contributors/SpikingChen/snn-arxiv-daily.svg?style=for-the-badge\n")
            f.write(f"[contributors-url]: https://github.com/SpikingChen/snn-arxiv-daily/graphs/contributors\n")
            f.write(f"[forks-shield]: https://img.shields.io/github/forks/SpikingChen/snn-arxiv-daily.svg?style=for-the-badge\n")
            f.write(f"[forks-url]: https://github.com/SpikingChen/snn-arxiv-daily/network/members\n")
            f.write(f"[stars-shield]: https://img.shields.io/github/stars/SpikingChen/snn-arxiv-daily.svg?style=for-the-badge\n")
            f.write(f"[stars-url]: https://github.com/SpikingChen/snn-arxiv-daily/stargazers\n")
            f.write(f"[issues-shield]: https://img.shields.io/github/issues/SpikingChen/snn-arxiv-daily.svg?style=for-the-badge\n")
            f.write(f"[issues-url]: https://github.com/SpikingChen/snn-arxiv-daily/issues\n\n")

    print("finished")


if __name__ == "__main__":

    data_collector = []
    data_collector_web= []

    keywords = dict()
    # 注意 OR 两侧必须有空格，否则不是合法的 arXiv query 语法
    keywords["Spiking Neural Network"]                 = "\"Spiking Neural Network\" OR \"Spiking Neural Networks\" OR \"Spiking Neuron\""

    for topic,keyword in keywords.items():

        # topic = keyword.replace("\"","")
        print("Keyword: " + topic)

        data,data_web = get_daily_papers(topic, query = keyword, max_results = 200)
        data_collector.append(data)
        data_collector_web.append(data_web)

        print("\n")

    # 1. update README.md file
    json_file = "snn-arxiv-daily.json"
    md_file   = "README.md"
    # update json data
    update_json_file(json_file,data_collector)
    # json data to markdown
    json_to_md(json_file,md_file)
