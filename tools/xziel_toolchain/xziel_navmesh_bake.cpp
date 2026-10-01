#include <Recast.h>
#include <DetourAlloc.h>
#include <DetourNavMesh.h>
#include <DetourNavMeshBuilder.h>
#include <DetourNavMeshQuery.h>

#include <algorithm>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

struct Mesh {
    std::vector<float> verts;
    std::vector<int> tris;
};

static int parse_index(const std::string& token, int nverts) {
    const size_t slash = token.find('/');
    const std::string head = slash == std::string::npos ? token : token.substr(0, slash);
    if (head.empty()) return -1;
    const int idx = std::stoi(head);
    return idx > 0 ? idx - 1 : nverts + idx;
}

static bool load_obj(const char* path, Mesh& mesh) {
    std::ifstream in(path);
    if (!in) return false;
    std::string line;
    while (std::getline(in, line)) {
        if (line.size() < 2) continue;
        if (line.rfind("v ", 0) == 0) {
            std::istringstream ss(line.substr(2));
            float x, y, z;
            if (ss >> x >> y >> z) {
                mesh.verts.push_back(x);
                mesh.verts.push_back(y);
                mesh.verts.push_back(z);
            }
        } else if (line.rfind("f ", 0) == 0) {
            std::istringstream ss(line.substr(2));
            std::vector<int> face;
            std::string token;
            const int nverts = int(mesh.verts.size() / 3);
            while (ss >> token) {
                const int idx = parse_index(token, nverts);
                if (idx < 0 || idx >= nverts) return false;
                face.push_back(idx);
            }
            if (face.size() >= 3) {
                for (size_t i = 1; i + 1 < face.size(); ++i) {
                    mesh.tris.push_back(face[0]);
                    mesh.tris.push_back(face[i]);
                    mesh.tris.push_back(face[i + 1]);
                }
            }
        }
    }
    return mesh.verts.size() >= 9 && mesh.tris.size() >= 3;
}

static void json_num(std::ostream& o, const char* key, double v, bool comma=true) {
    o << "  \"" << key << "\": " << v << (comma ? "," : "") << "\n";
}

int main(int argc, char** argv) {
    if (argc != 4) {
        std::cerr << "usage: xziel-navmesh-bake INPUT.obj OUTPUT.navbin REPORT.json\n";
        return 2;
    }

    Mesh mesh;
    if (!load_obj(argv[1], mesh)) {
        std::cerr << "XZIEL_NAVMESH_FAIL: could not parse OBJ\n";
        return 3;
    }

    const int nverts = int(mesh.verts.size() / 3);
    const int ntris = int(mesh.tris.size() / 3);
    float bmin[3], bmax[3];
    rcCalcBounds(mesh.verts.data(), nverts, bmin, bmax);

    rcContext ctx(true);
    rcConfig cfg{};
    cfg.cs = 0.15f;
    cfg.ch = 0.10f;
    cfg.walkableSlopeAngle = 50.0f;
    const float agentHeight = 1.80f;
    const float agentRadius = 0.34f;
    const float agentClimb = 0.45f;
    cfg.walkableHeight = int(std::ceil(agentHeight / cfg.ch));
    cfg.walkableClimb = int(std::floor(agentClimb / cfg.ch));
    cfg.walkableRadius = int(std::ceil(agentRadius / cfg.cs));
    cfg.maxEdgeLen = int(12.0f / cfg.cs);
    cfg.maxSimplificationError = 1.3f;
    cfg.minRegionArea = int(rcSqr(8.0f));
    cfg.mergeRegionArea = int(rcSqr(20.0f));
    cfg.maxVertsPerPoly = 6;
    cfg.detailSampleDist = cfg.cs * 6.0f;
    cfg.detailSampleMaxError = cfg.ch * 1.0f;
    rcVcopy(cfg.bmin, bmin);
    rcVcopy(cfg.bmax, bmax);
    rcCalcGridSize(cfg.bmin, cfg.bmax, cfg.cs, &cfg.width, &cfg.height);

    rcHeightfield* solid = rcAllocHeightfield();
    rcCompactHeightfield* chf = nullptr;
    rcContourSet* cset = nullptr;
    rcPolyMesh* pmesh = nullptr;
    rcPolyMeshDetail* dmesh = nullptr;
    dtNavMesh* nav = nullptr;
    dtNavMeshQuery* query = nullptr;
    std::vector<unsigned char> areas(size_t(ntris), 0);

    auto fail = [&](const char* msg, int code) {
        std::cerr << "XZIEL_NAVMESH_FAIL: " << msg << "\n";
        if (query) dtFreeNavMeshQuery(query);
        if (nav) dtFreeNavMesh(nav);
        if (dmesh) rcFreePolyMeshDetail(dmesh);
        if (pmesh) rcFreePolyMesh(pmesh);
        if (cset) rcFreeContourSet(cset);
        if (chf) rcFreeCompactHeightfield(chf);
        if (solid) rcFreeHeightField(solid);
        return code;
    };

    if (!solid) return fail("heightfield allocation", 10);
    if (!rcCreateHeightfield(&ctx, *solid, cfg.width, cfg.height, cfg.bmin, cfg.bmax, cfg.cs, cfg.ch))
        return fail("heightfield creation", 11);

    rcMarkWalkableTriangles(&ctx, cfg.walkableSlopeAngle, mesh.verts.data(), nverts,
                            mesh.tris.data(), ntris, areas.data());
    if (!rcRasterizeTriangles(&ctx, mesh.verts.data(), nverts, mesh.tris.data(),
                              areas.data(), ntris, *solid, cfg.walkableClimb))
        return fail("triangle rasterization", 12);

    rcFilterLowHangingWalkableObstacles(&ctx, cfg.walkableClimb, *solid);
    rcFilterLedgeSpans(&ctx, cfg.walkableHeight, cfg.walkableClimb, *solid);
    rcFilterWalkableLowHeightSpans(&ctx, cfg.walkableHeight, *solid);

    chf = rcAllocCompactHeightfield();
    if (!chf) return fail("compact heightfield allocation", 13);
    if (!rcBuildCompactHeightfield(&ctx, cfg.walkableHeight, cfg.walkableClimb, *solid, *chf))
        return fail("compact heightfield build", 14);
    rcFreeHeightField(solid);
    solid = nullptr;

    if (!rcErodeWalkableArea(&ctx, cfg.walkableRadius, *chf))
        return fail("walkable erosion", 15);
    if (!rcBuildDistanceField(&ctx, *chf))
        return fail("distance field", 16);
    if (!rcBuildRegions(&ctx, *chf, 0, cfg.minRegionArea, cfg.mergeRegionArea))
        return fail("regions", 17);

    cset = rcAllocContourSet();
    if (!cset) return fail("contour allocation", 18);
    if (!rcBuildContours(&ctx, *chf, cfg.maxSimplificationError, cfg.maxEdgeLen, *cset))
        return fail("contours", 19);

    pmesh = rcAllocPolyMesh();
    if (!pmesh) return fail("poly mesh allocation", 20);
    if (!rcBuildPolyMesh(&ctx, *cset, cfg.maxVertsPerPoly, *pmesh))
        return fail("poly mesh", 21);
    if (pmesh->npolys <= 0 || pmesh->nverts <= 0)
        return fail("empty poly mesh", 22);

    dmesh = rcAllocPolyMeshDetail();
    if (!dmesh) return fail("detail mesh allocation", 23);
    if (!rcBuildPolyMeshDetail(&ctx, *pmesh, *chf, cfg.detailSampleDist,
                               cfg.detailSampleMaxError, *dmesh))
        return fail("detail mesh", 24);

    for (int i = 0; i < pmesh->npolys; ++i) {
        if (pmesh->areas[i] == RC_WALKABLE_AREA) pmesh->areas[i] = 0;
        pmesh->flags[i] = 1;
    }

    dtNavMeshCreateParams params{};
    params.verts = pmesh->verts;
    params.vertCount = pmesh->nverts;
    params.polys = pmesh->polys;
    params.polyAreas = pmesh->areas;
    params.polyFlags = pmesh->flags;
    params.polyCount = pmesh->npolys;
    params.nvp = pmesh->nvp;
    params.detailMeshes = dmesh->meshes;
    params.detailVerts = dmesh->verts;
    params.detailVertsCount = dmesh->nverts;
    params.detailTris = dmesh->tris;
    params.detailTriCount = dmesh->ntris;
    params.walkableHeight = agentHeight;
    params.walkableRadius = agentRadius;
    params.walkableClimb = agentClimb;
    rcVcopy(params.bmin, pmesh->bmin);
    rcVcopy(params.bmax, pmesh->bmax);
    params.cs = cfg.cs;
    params.ch = cfg.ch;
    params.buildBvTree = true;

    unsigned char* navData = nullptr;
    int navDataSize = 0;
    if (!dtCreateNavMeshData(&params, &navData, &navDataSize) || !navData || navDataSize <= 0)
        return fail("Detour data build", 25);

    {
        std::ofstream out(argv[2], std::ios::binary);
        if (!out) {
            dtFree(navData);
            return fail("nav output open", 26);
        }
        out.write(reinterpret_cast<const char*>(navData), navDataSize);
        if (!out.good()) {
            dtFree(navData);
            return fail("nav output write", 27);
        }
    }

    nav = dtAllocNavMesh();
    if (!nav) {
        dtFree(navData);
        return fail("Detour navmesh allocation", 28);
    }
    dtStatus status = nav->init(navData, navDataSize, DT_TILE_FREE_DATA);
    if (dtStatusFailed(status)) {
        dtFree(navData);
        return fail("Detour navmesh init", 29);
    }

    query = dtAllocNavMeshQuery();
    if (!query) return fail("Detour query allocation", 30);
    status = query->init(nav, 2048);
    if (dtStatusFailed(status)) return fail("Detour query init", 31);

    const float center[3] = {
        (bmin[0] + bmax[0]) * 0.5f,
        (bmin[1] + bmax[1]) * 0.5f,
        (bmin[2] + bmax[2]) * 0.5f
    };
    const float ext[3] = {
        std::max(2.0f, (bmax[0]-bmin[0]) * 0.5f),
        std::max(4.0f, (bmax[1]-bmin[1]) * 0.5f),
        std::max(2.0f, (bmax[2]-bmin[2]) * 0.5f)
    };
    dtQueryFilter filter;
    dtPolyRef nearestRef = 0;
    float nearest[3]{};
    status = query->findNearestPoly(center, ext, &filter, &nearestRef, nearest);
    if (dtStatusFailed(status) || nearestRef == 0)
        return fail("Detour nearest-poly validation", 32);

    std::ofstream report(argv[3]);
    if (!report) return fail("report output open", 33);
    report << "{\n";
    report << "  \"status\": \"PASS\",\n";
    json_num(report, "input_vertices", nverts);
    json_num(report, "input_triangles", ntris);
    json_num(report, "grid_width", cfg.width);
    json_num(report, "grid_height", cfg.height);
    json_num(report, "nav_vertices", pmesh->nverts);
    json_num(report, "nav_polygons", pmesh->npolys);
    json_num(report, "detail_vertices", dmesh->nverts);
    json_num(report, "detail_triangles", dmesh->ntris);
    json_num(report, "navdata_bytes", navDataSize);
    json_num(report, "agent_height", agentHeight);
    json_num(report, "agent_radius", agentRadius);
    json_num(report, "agent_climb", agentClimb);
    json_num(report, "walkable_slope_degrees", cfg.walkableSlopeAngle);
    report << "  \"nearest_poly_ref\": " << static_cast<unsigned long long>(nearestRef) << "\n";
    report << "}\n";
    report.close();

    std::cout << "XZIEL_RECAST_DETOUR_NAVMESH_PASS\n";
    std::cout << "NAV_POLYGONS " << pmesh->npolys << "\n";
    std::cout << "NAV_VERTICES " << pmesh->nverts << "\n";
    std::cout << "NAVDATA_BYTES " << navDataSize << "\n";

    dtFreeNavMeshQuery(query);
    query = nullptr;
    dtFreeNavMesh(nav);
    nav = nullptr;
    rcFreePolyMeshDetail(dmesh);
    dmesh = nullptr;
    rcFreePolyMesh(pmesh);
    pmesh = nullptr;
    rcFreeContourSet(cset);
    cset = nullptr;
    rcFreeCompactHeightfield(chf);
    chf = nullptr;
    return 0;
}
