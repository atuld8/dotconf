#!/bin/bash
df -khP . | tail -1 | awk '{ print $5 }'
