<template>
    <v-card
    class="flex-column flex-nowrap"
    v-bind:class="{'d-flex': isContainerFlex, 'd-none': isContainerNone }"
    max-width="100%"
    elevation="2"
    :scrollable="false"
    >
        <v-card-title>
            <span class="text-h5">Plot visualization</span>
            <v-menu>
                <template v-slot:activator="{on, attrs}">
                    <v-btn icon v-bind="attrs" v-on="on">
                        <v-icon>mdi-dots-vertical</v-icon>
                    </v-btn>
                </template>
                <v-list>
                    <v-list-item link>
                        Download?
                    </v-list-item>
                </v-list>
            </v-menu>
        </v-card-title>
        <v-card-text >
            <svg id="graph"></svg>
        </v-card-text>
    </v-card>
</template>

<script>

import * as d3 from "d3";
import { useTimelineStore } from "@/store/timeline";
import { mapStores } from "pinia";
import Plotly from 'plotly.js';

const width = 640;
const height = 400;
const marginTop = 20;
const marginRight = 30;
const marginBottom = 30;
const marginLeft = 40;

export default {
    data() {
        return {
            isContainerFlex: true,
            isContainerNone: false,
            plotData: [
            {
                x: [1, 2, 3, 4, 5],
                y: [1, 4, 9, 16, 25],
                type: 'scatter',
            },
            ],
            plotLayout: {
                title: 'Line Plot',
                xaxis: { title: 'X-axis' },
                yaxis: { title: 'Y-axis' },
            },
        };
    },
    methods: {
        mapLinePath(data, scalers, dataMapping) {
            return
        },

    },
    mounted: {
        createChart() {
            Plotly.newPlot('chart-container', this.plotData, this.plotLayout);
        },
    },
    computed: {
        visualizationData() {
            console.log(this.timelineStore.getVisualizationData)
            return this.timelineStore.getVisualizationData;
        },
        displayVisualization() {
            if (this.visualizationData === null) {
                this.isContainerFlex = false;
                this.isContainerNone = true;
            } else {
                this.isContainerFlex = true;
                this.isContainerNone = false;
            }
        },
        ...mapStores(
            useTimelineStore,
        )
    },
    watch: {
        visualizationData: {
            handler(newData) {
                if (newData === null) {
                    return;
                }
                const xData = newData["plotData"]["result"]["data"][newData["xMapping"]];
                const yData = newData["plotData"]["result"]["data"][newData["yMapping"]];

                // Declare the x (horizontal position) scale.
                const x = d3.scaleLinear(d3.extent(xData), [marginLeft, width - marginRight]);

                // Declare the y (vertical position) scale.
                const y = d3.scaleLinear(d3.extent(yData), [height - marginBottom, marginTop]);

                const svg = d3.select("#graph")
                            .attr("width", width)
                            .attr("height", height)
                            .attr("viewBox", [0, 0, width, height])
                            .attr("style", "max-width: 100%; height: auto; height: intrinsic;");

                const path = d3.line();

                const data = xData.map((d, i) => {
                    return [x(d), y(yData[i])];
                });


                const pointerLine = svg.append("line")
                    .attr("x1", 0)
                    .attr("y1", 0)
                    .attr("stroke", "black")
                    .attr("y2", height);

                svg.on("mousemove", (event) => {
                    const points = d3.pointer(event);
                    let datapoint = [0, 0];
                    for (let i = 0; i < data.length; i++) {
                        if (Math.abs(points[0] - data[i][0]) < Math.abs(points[0] - datapoint[0])) {
                            datapoint = data[i];
                        }
                    }
                    pointerLine.attr("x1", points[0]);
                    pointerLine.attr("x2", points[0]);
                    pointerLine.attr("y2", datapoint[1]);
                });

                svg.append("g")
                    .attr("transform", `translate(0,${height - marginBottom})`)
                    .call(d3.axisBottom(x).ticks(width / 80).tickSizeOuter(0));

                svg.append("g")
                    .attr("transform", `translate(${marginLeft},0)`)
                    .call(d3.axisLeft(y).ticks(height / 40))
                    .call(g => g.select(".domain").remove())
                    .call(g => g.selectAll(".tick line").clone()
                        .attr("x2", width - marginLeft - marginRight)
                        .attr("stroke-opacity", 0.1));


                svg.append("path")
                    .attr("fill", "none")
                    .attr("stroke", "steelblue")
                    .attr("stroke-width", 1.5)
                    .attr("d", path(data));
            }
        }
    }
}
</script>
