import datetime
import requests
import json
import arxiv
import os

base_url = "https://arxiv.paperswithcode.com/api/v0/papers/"

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

def get_daily_papers(topic,query="SNN", max_results=2):
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
    
    search_engine = arxiv.Search(
        query = query,
        max_results = max_results,
        sort_by = arxiv.SortCriterion.SubmittedDate
    )

    cnt = 0

    for result in search_engine.results():

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
            comments = None
            if comments != None:
                content_to_web[paper_key] = content_to_web[paper_key] + f", {comments}\n"
            else:
                content_to_web[paper_key] = content_to_web[paper_key] + f"\n"

        except Exception as e:
            print(f"exception: {e} with id: {paper_key}")

    sorted_content = dict(sorted(content.items(), key=lambda x: x[1].split('|')[1], reverse=True))
    sorted_content_to_web = dict(sorted(content_to_web.items(), key=lambda x: x[1].split(',')[0], reverse=True))
                  
    data = {topic:sorted_content}
    data_web = {topic:content_to_web}
    return data, data_web 

def update_json_file(filename,data_all):
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

    with open(filename,"w") as f:
        json.dump(json_data,f)
    
def json_to_md(filename,md_filename,
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
    keywords["Spiking Neural Network"]                 = "\"Spiking Neural Network\"OR\"Spiking Neural Networks\"OR\"Spiking Neuron\""

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




