#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshQuery.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

struct Probe {
    std::string name;
    float p[3]{};
    dtPolyRef ref = 0;
    float nearest[3]{};
    float horizontal = 0.0f;
    float vertical = 0.0f;
    float distance = 0.0f;
    bool pass = false;
};

static std::string safe_name(std::string s) {
    for (char& c : s) {
        if (!((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
              (c >= '0' && c <= '9') || c == '_' || c == '-')) c = '_';
    }
    return s;
}

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: xziel-navmesh-probe NAVBIN PROBES.txt REPORT.json\n";
        return 2;
    }

    std::ifstream navIn(argv[1], std::ios::binary | std::ios::ate);
    if (!navIn) {
        std::cerr << "XZIEL_NAV_PROBE_FAIL: navbin open\n";
        return 3;
    }
    const std::streamsize navSize = navIn.tellg();
    if (navSize <= 0) {
        std::cerr << "XZIEL_NAV_PROBE_FAIL: empty navbin\n";
        return 4;
    }
    navIn.seekg(0, std::ios::beg);

    unsigned char* navData = static_cast<unsigned char*>(dtAlloc(size_t(navSize), DT_ALLOC_PERM));
    if (!navData) {
        std::cerr << "XZIEL_NAV_PROBE_FAIL: allocation\n";
        return 5;
    }
    if (!navIn.read(reinterpret_cast<char*>(navData), navSize)) {
        dtFree(navData);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: navbin read\n";
        return 6;
    }

    dtNavMesh* nav = dtAllocNavMesh();
    if (!nav) {
        dtFree(navData);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: navmesh allocation\n";
        return 7;
    }
    dtStatus status = nav->init(navData, int(navSize), DT_TILE_FREE_DATA);
    if (dtStatusFailed(status)) {
        dtFree(navData);
        dtFreeNavMesh(nav);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: navmesh init\n";
        return 8;
    }

    dtNavMeshQuery* query = dtAllocNavMeshQuery();
    if (!query) {
        dtFreeNavMesh(nav);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: query allocation\n";
        return 9;
    }
    status = query->init(nav, 4096);
    if (dtStatusFailed(status)) {
        dtFreeNavMeshQuery(query);
        dtFreeNavMesh(nav);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: query init\n";
        return 10;
    }

    std::ifstream pin(argv[2]);
    if (!pin) {
        dtFreeNavMeshQuery(query);
        dtFreeNavMesh(nav);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: probe file open\n";
        return 11;
    }

    std::vector<Probe> probes;
    std::string line;
    while (std::getline(pin, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ss(line);
        Probe p;
        if (!(ss >> p.name >> p.p[0] >> p.p[1] >> p.p[2])) continue;
        p.name = safe_name(p.name);
        probes.push_back(p);
    }
    if (probes.size() < 2) {
        dtFreeNavMeshQuery(query);
        dtFreeNavMesh(nav);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: need at least two probes\n";
        return 12;
    }

    dtQueryFilter filter;
    const float ext[3] = {1.50f, 0.90f, 1.50f};
    bool allProbes = true;
    for (Probe& p : probes) {
        status = query->findNearestPoly(p.p, ext, &filter, &p.ref, p.nearest);
        if (dtStatusFailed(status) || p.ref == 0) {
            p.pass = false;
            allProbes = false;
            continue;
        }
        const float dx = p.nearest[0] - p.p[0];
        const float dy = p.nearest[1] - p.p[1];
        const float dz = p.nearest[2] - p.p[2];
        p.horizontal = std::sqrt(dx*dx + dz*dz);
        p.vertical = std::fabs(dy);
        p.distance = std::sqrt(dx*dx + dy*dy + dz*dz);
        p.pass = p.horizontal <= 1.50f && p.vertical <= 0.90f;
        allProbes = allProbes && p.pass;
    }

    struct Link {
        std::string from;
        std::string to;
        int pathPolys = 0;
        bool pass = false;
    };
    std::vector<Link> links;
    bool allLinks = true;
    for (size_t i = 0; i + 1 < probes.size(); ++i) {
        Link link{probes[i].name, probes[i+1].name, 0, false};
        if (probes[i].pass && probes[i+1].pass) {
            dtPolyRef path[512]{};
            int pathCount = 0;
            status = query->findPath(
                probes[i].ref, probes[i+1].ref,
                probes[i].nearest, probes[i+1].nearest,
                &filter, path, &pathCount, 512
            );
            link.pathPolys = pathCount;
            link.pass = !dtStatusFailed(status) && pathCount > 0;
        }
        allLinks = allLinks && link.pass;
        links.push_back(link);
    }

    std::ofstream out(argv[3]);
    if (!out) {
        dtFreeNavMeshQuery(query);
        dtFreeNavMesh(nav);
        std::cerr << "XZIEL_NAV_PROBE_FAIL: report open\n";
        return 13;
    }

    out << "{\n";
    out << "  \"status\": \"" << ((allProbes && allLinks) ? "PASS" : "FAIL") << "\",\n";
    out << "  \"all_probes_pass\": " << (allProbes ? "true" : "false") << ",\n";
    out << "  \"all_links_pass\": " << (allLinks ? "true" : "false") << ",\n";
    out << "  \"probes\": [\n";
    for (size_t i = 0; i < probes.size(); ++i) {
        const Probe& p = probes[i];
        out << "    {\n";
        out << "      \"name\": \"" << p.name << "\",\n";
        out << "      \"input\": [" << p.p[0] << ", " << p.p[1] << ", " << p.p[2] << "],\n";
        out << "      \"poly_ref\": " << static_cast<unsigned long long>(p.ref) << ",\n";
        out << "      \"nearest\": [" << p.nearest[0] << ", " << p.nearest[1] << ", " << p.nearest[2] << "],\n";
        out << "      \"horizontal_error\": " << p.horizontal << ",\n";
        out << "      \"vertical_error\": " << p.vertical << ",\n";
        out << "      \"distance\": " << p.distance << ",\n";
        out << "      \"pass\": " << (p.pass ? "true" : "false") << "\n";
        out << "    }" << (i + 1 < probes.size() ? "," : "") << "\n";
    }
    out << "  ],\n";
    out << "  \"links\": [\n";
    for (size_t i = 0; i < links.size(); ++i) {
        const Link& l = links[i];
        out << "    {\n";
        out << "      \"from\": \"" << l.from << "\",\n";
        out << "      \"to\": \"" << l.to << "\",\n";
        out << "      \"path_polygons\": " << l.pathPolys << ",\n";
        out << "      \"pass\": " << (l.pass ? "true" : "false") << "\n";
        out << "    }" << (i + 1 < links.size() ? "," : "") << "\n";
    }
    out << "  ]\n";
    out << "}\n";

    for (const Probe& p : probes) {
        std::cout << "NAV_PROBE " << p.name
                  << " REF " << static_cast<unsigned long long>(p.ref)
                  << " HERR " << p.horizontal
                  << " VERR " << p.vertical
                  << " PASS " << (p.pass ? 1 : 0) << "\n";
    }
    for (const Link& l : links) {
        std::cout << "NAV_PATH " << l.from << "->" << l.to
                  << " POLYS " << l.pathPolys
                  << " PASS " << (l.pass ? 1 : 0) << "\n";
    }

    dtFreeNavMeshQuery(query);
    dtFreeNavMesh(nav);

    if (!(allProbes && allLinks)) {
        std::cerr << "XZIEL_NAVMESH_CONNECTIVITY_FAIL\n";
        return 20;
    }
    std::cout << "XZIEL_NAVMESH_CONNECTIVITY_PASS\n";
    return 0;
}
