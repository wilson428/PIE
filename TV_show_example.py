'''
See DOCUMENTATION for overview and LICENSE for license
Corrections and coding advice always welcome! cewilson@yahoo-inc.com
'''

#DISCLAIMER:This exampel is VERY sloppy. I work on deadline.

#the text analyzed here was downloaded from this Document Cloud repo:
#http://www.documentcloud.org/api/search.json?q=contributedto:freethefiles&page=1


import urllib2, json, re, sqlite3, math
import nltk
from itertools import groupby
import difflib

def ordered_set(seq):
    seen = set()
    seen_add = seen.add
    return [ x for x in seq if x.lower() not in seen and not seen_add(x.lower())]

#we're going to use a Predictable Information Elimination algorithm to reduce the forms to significant information

#STEP 1: Construct definitions of known info types
#A better way might be to look at works with high colocation across documents
#Note: This method is generally tolerate of false positives in these definitions if the data is sufficiently noisy

patterns = [
    ["phone", "\(\d{3}\)\s{0,1}\d{3}\-\d{4}"],
    ["station", "(^(W|K)[A-Z]{3}|\s(W|K)[A-Z]{3})(?![A-z])"],
    ["date", "\d{1,2}/\d{1,2}/\d{2,4}"],
    ["date", "\d{1,2}\|\d{1,2}\|\d{2,4}"],
    ["date", "\d{2}I\d{2}I\d{2,4}"],
    ["date", "MON|TUE|TUES|WED|THU|FRI|SAT|SUN"],     
    ["date", "mon|tue|tues|wed|thu|fri|sat|sun"],
    ["date", "Mon|Tue|Tues|Wed|Thur|Fri|Sat|Sun"],
    ["date", "MO|TU|WE|TH|FR|SA|SU"],
    ["money", "\$[\d,\.]+" ],    
    ["time", "\d[\d:-]{0,5}\s{0,1}[APXap]{1,2}[Mm]{0,1}"],
    ["stop", "\d{5,100}"],
    ["stop", "\dX"],
    ["stop", "[A-Z] \d+"],
    ["schedule", "[MTuWhFS/-]{5,15}"],
    ["schedule", "[MTuWhFS]{1,2}-[MTuWhFS]{1,2}"]   
]

#don't do this
stops = ["Rating","Weekday",":30",":15","Week","Class", "PRIME", "Material","Comment","Prime","Contract","Rtg","CDR","WRC","EF","LN","Estimate","Product","Month","Amount","Rate","IP","CA","CM","NM","Type","Length","Sale","Totals","Total","Start","End","Date","Spot","Printed", "Print","Page","Description"]

#STEP 2: Define method of removing predictable information from the corpus. This could be anything from visually marking them to deleting them
#In this case, we wrap known types in <span> tags and assign them classes for viewing online. The pointy brackets in the tag serve the added purpose of marking off predictable info

def add_class(name):
    def repl(match):
        return "<span class='%s'>" % name + match.group(0) + "</span>"    
    return repl

def tag_show(name):
    def repl(match):
        #matches.append(name)
        return "<span class='show'>%s</span>" % name
    return repl

#STEP 3: Define a filter to encompass all possible candidates for the unpredictable info we want.

'''
candidate_pattern1 = ">( [A-z0-9\/: ]+ )<"
candidate_pattern2 = "^([A-z0-9\/: ]+ )<"
candidate_pattern3 = ">( [A-z0-9\/: ]+)"
'''

#candidate_pattern1 = "/span>(.*?)<"
candidate_pattern1 = "/span>(.*?)<"


#STEP 3.1: Prepare the candidate string--what's left after the first two steps--for evaluation
def stage(candidate):
    candidate = re.sub("\(.*?\)", "", candidate)
    candidate = re.sub("[\:\,]", "", candidate)
    candidate = candidate.split("/")[0]
    return " ".join(ordered_set(re.split("[\n\s-]+", candidate))).strip()

#STEP 3.2: Define a method for guessing whether a candidate string--what's left after the first two steps--is what we want
def check_candidate(match):
    if len(match.group(1)) > 3 and len(match.group(1)) < 50 and re.sub('[0-9\s]+', '', match.group(1)) != "":
        candidates.append(match.group(1))
        return "/span><span class='candidate'>" + match.group(1) + "</span><"   
    return match.group(0)

#STEP 4: Build a lexicon based on results. In this case, this is a SQLite database called "shows" passed to the function.
#As shows are detected and added to the database, it catches more and more.

def markup(ad, shows):
    global candidates
    candidates = []
    matches = []
    submatches = []
    news = []
    sports = []
    orphans = []

    lines = ad['text']

    #STEP 1-2
    #apply stop words
    for word in stops:
        #VERY crude -- attempt plurals and past participles first
        lines = re.sub(word + "s", add_class("stop"), lines)
        lines = re.sub(word + "ed", add_class("stop"), lines)
        lines = re.sub(word, add_class("stop"), lines)

    #apply patterns
    for pattern in patterns:
        lines = re.sub(pattern[1], add_class(pattern[0]), lines)

    #STEP 3
    #identify candidates
    lines = re.sub(candidate_pattern1, check_candidate, lines, flags=re.DOTALL)
    #lines = re.sub(candidate_pattern2, check_candidate, lines, flags=re.DOTALL)
    #lines = re.sub(candidate_pattern3, check_candidate, lines)

    #STEP 4
    for candidate in set(candidates):
        clean_candidate = stage(candidate)
        found = False
        for show in shows:
            name = show['name']
            variants = show['variants'].split(",")
            variants.insert(0, name)
            for variant in variants:
                if variant == "":
                    break
                metric = difflib.SequenceMatcher(a=variant.lower(), b=clean_candidate.lower()).ratio()
                if len(clean_candidate) < 10:
                    metric -= 0.1
                
                if metric >= 0.7:
                    #print "MATCH",variant,clean_candidate, metric
                    lines = lines.replace("<span class='candidate'>%s</span>" % candidate, "<span class='show'>%s</span>" % name)
                    matches.append(name)
                    found = True
                    break
            if found:
                break

        if not found:
            #print "NOT FOUND",candidate
            if "news" in clean_candidate.lower():
                #print "NEWS",clean_candidate
                news.append(clean_candidate)
                lines = lines.replace("<span class='candidate'>%s</span>" % candidate, "<span class='news'>%s</span>" % clean_candidate)
                found = True
            elif "sports" in clean_candidate.lower() or "ball" in clean_candidate.lower() or "nfl" in clean_candidate.lower():
                #print "SPORTS",clean_candidate
                sports.append(clean_candidate)
                lines = lines.replace("<span class='candidate'>%s</span>" % candidate, "<span class='sports'>%s</span>" % clean_candidate)
                found = True
                
        if not found:                                          
            orphans.append(clean_candidate)

    lines = re.sub("\n+", "<br />", lines)
    html = lines
    candidates = orphans

    
    return {
        'html': html,
        'candidates':sorted(set(candidates)),
        'matches': sorted(matches),
        'news': sorted(news),
        'sports': sorted(sports)
    }
