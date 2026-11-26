#!/bin/bash
set -euo pipefail
export LC_ALL=C
count=${1:-10}
stat=${2:-min}
[[ $stat == min || $stat == avg ]] || exit 2
[[ $count =~ ^([1-9]|10)$ ]] || exit 2
/usr/bin/nettop -n -m tcp -p WeChat -L "$count" -s 1 -J interface,state,rtt_avg | /usr/bin/awk -v stat="$stat" -F, '
function finish_sample() {
    if (n) { total += sum/n; samples++ }
    n=0; sum=0
}
$1 == "" {
    finish_sample()
    for (i=1; i<=NF; i++) col[$i]=i
    next
}
$1 ~ /^ *tcp[46] / && col["state"] && col["interface"] && col["rtt_avg"] {
    value=$(col["rtt_avg"])
    if ($(col["state"]) == "Established" && $(col["interface"]) !~ /^lo[0-9]/ &&
        value ~ /^[ ]*[0-9]+([.][0-9]+)? ms[ ]*$/ && value+0 > 0) {
        sum+=value; n++
        if (value+0 > maximum) maximum=value+0
        if (!minimum || value+0 < minimum) minimum=value+0
    }
}
END {
    finish_sample()
    if (!samples) { print "没有可用的微信 TCP RTT" > "/dev/stderr"; exit 1 }
    mean=total/samples
    printf "微信 RTT：最低 %.2f ms，最高 %.2f ms，平均 %.2f ms（%d 次有效采样）\n", minimum,maximum,mean,samples > "/dev/stderr"
    chosen=(stat=="avg" ? mean : minimum)
    lead=int(chosen/4)-5
    if (lead<0 || samples<3) lead=0
    if (lead>15) lead=15
    printf "采用%s RTT %.2f ms，网络提前量 %d ms\n",(stat=="avg" ? "平均" : "最低"),chosen,lead > "/dev/stderr"
    printf "%d\n",lead
}'
