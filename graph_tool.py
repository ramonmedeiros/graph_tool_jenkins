#!/usr/bin/env python

#
#  Arguments
#  sys.argv[1] JOBS: For example, https://jenkins/myJob
#
#   The script will iterate over last jobs and get results in a graph
#
#  @returns: URL to job artifact
#

from os.path import basename
from plotly.offline.offline import plot
from urllib import urlopen

import requests, json, sys, threading
import plotly.graph_objs as go

# jenkins REST API
RUNS = "/api/json?tree=builds[number]"
ROBOT_API = "/robot/api/json"

# other constants
ALL = "all"
FAILED = "failed"
PASSED = "passed"
PERCENT = "percent"
CRITICAL = "Critical tests"
ALL_TESTS = "All tests"

def _do_get(url, retry=2):
    """
    Returns response from URL
    """
    # retry in case of failure
    for i in range(2):
        try:
            content = urlopen(url)
            if content.code == 404:
                return None
        except Exception:
            return None
        return content.read()

def _get_json(url):
    """
    Returns dict from URL
    """
    try:
        return json.loads(_do_get(url))
    except Exception:
        return None

def get_runs(job_url):
    runsList = _get_json(job_url + RUNS)

    # nothing returned: return empty
    if runsList == {}:
        return None

    # get builds
    builds = []
    for build in runsList['builds']:
        builds.append(build.get('number'))

    return builds

def get_pass_rate_api(url, buildId, returnDict):
    
    job_url = "%s/%d" % (url, buildId)
    robotApi = _get_json(job_url + ROBOT_API)

    # return empty
    if robotApi == None:
        return {}

    criticalPercent = (float(robotApi.get("criticalPassed")) / float(robotApi.get("criticalTotal"))) * 100
    allPercent = (float(robotApi.get("overallPassed")) / float(robotApi.get("overallTotal"))) * 100

    returnDict[buildId] = {CRITICAL: {ALL: robotApi.get("criticalTotal"),
                                      PASSED: robotApi.get("criticalPassed"),
                                      FAILED: robotApi.get("criticalFailed"),
                                      PERCENT: criticalPercent},
                           ALL_TESTS: {ALL: robotApi.get("overallTotal"),
                                       PASSED: robotApi.get("overallPassed"),
                                       FAILED: robotApi.get("overallFailed"),
                                       PERCENT: allPercent}
                        }

def plot_graph(jobs):

    # iterate over all jobs and creater scatters
    results = {}
    lines = []
    for job in jobs.keys():

        critical = []
        names = []
        for run in sorted(jobs[job]):
            
            if CRITICAL in jobs[job][run] and ALL_TESTS in jobs[job][run]:
                critical.append(jobs[job][run][CRITICAL][PERCENT])
                names.append("%s/%s" % (job, run))
        results[job] = {}
        results[job]['percent'] = critical
        results[job]['names'] = names

    # iterate and get greater
    size = 0
    for job in results:
        if size < len(results[job]['percent']):
            size = len(results[job]['percent'])

    # create lines
    for job in results:
        lines.append(go.Scatter(x=range(size - len(results[job]['percent']), size),
                                y=results[job]['percent'],
                                text=results[job]['names'],
                                name='%s - %s' % (job, CRITICAL),
                                mode="lines+markers"))

    data=go.Data(lines)
    layout=go.Layout(title="Regression Status", xaxis={'title':'Last Builds'}, yaxis={'title':'Percent', 'range':[0,100]})
    figure=go.Figure(data=data,layout=layout)
    plot(figure, filename='test.html',  auto_open=True)

def getResults(job, testsResults):
    
    # job name
    if job[-1:] == '/':
        job = job[:-1]
    job_name = basename(job)
    testsResults[job_name] = {}

    # not acessible: continue
    builds = get_runs(job)

    # create threads to get passrate
    threadList = []
    for build in builds:
        threadList.append(threading.Thread(target=get_pass_rate_api, args=(job, build, testsResults[job_name],)))

    # start threads
    for thread in threadList:
        thread.start()

    # wait to finish
    for thread in threadList:
        thread.join()


def main():
    # url is passed: iterate over jobs
    if len(sys.argv) > 1 and len(sys.argv[1]) > 1:
        jobs = sys.argv[1:]

        # create threads for each job
        testsResults = {}
        threadList = []
        for job in jobs:
            threadList.append(threading.Thread(target=getResults, args=(job, testsResults,)))

        # start threads
        for thread in threadList:
           thread.start()

        # wait to finish
        for thread in threadList:
            thread.join()

        plot_graph(testsResults)
    sys.exit(1)
main()
