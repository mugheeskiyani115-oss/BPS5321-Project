"""Source-conscious site profiles and printable 3D geospatial figure for BioTwin PDFs.

When possible, a browser capture from the actual BioTwin Results 3D map is used.
A generated schematic is a *modelled data visual*, not a photo, aerial image,
site survey or a map depicting the true height of buildings or trees.

Optional resident statistics: data/demographics_planning_area.csv from SingStat.
No unverified demographic figures are inserted.
"""
from __future__ import annotations

import base64
import io
import math
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CENSUS = ROOT / 'data' / 'demographics_planning_area.csv'
CENSUS_REFERENCE = ('Singapore Department of Statistics, Population Trends 2025, '
                    'https://www.singstat.gov.sg/-/media/files/publications/population/population2025.pdf')


def _closest_area(areas: pd.DataFrame, site: dict):
    x, y = float(site['lon']), float(site['lat'])
    dx = (areas.longitude.to_numpy(float) - x) * math.cos(math.radians(y))
    dy = areas.latitude.to_numpy(float) - y
    k = int(np.argmin(dx * dx + dy * dy))
    return areas.iloc[k]


def _in_ring(point, ring):
    x,y=point
    inside=False
    if len(ring)<4: return False
    for j in range(len(ring)):
        xi,yi=ring[j-1][0],ring[j-1][1]
        xj,yj=ring[j][0],ring[j][1]
        if (yi>y)!=(yj>y):
            xx=(xj-xi)*(y-yi)/(yj-yi)+xi
            if x<xx:inside=not inside
    return inside


def _polygon_contains(coords, point):
    if not coords or not _in_ring(point, coords[0]):return False
    return not any(_in_ring(point,hole) for hole in coords[1:])


def _area_for_point(bundle, site):
    """Official 2019 planning polygon when supplied; nearest centroid only as fallback."""
    target=(float(site['lon']),float(site['lat']))
    geo=getattr(bundle,'geojson',None)
    if isinstance(geo,dict):
        for f in geo.get('features',[]):
            geom=f.get('geometry') or {}
            typ=geom.get('type'); coords=geom.get('coordinates') or []
            polys=[coords] if typ=='Polygon' else coords if typ=='MultiPolygon' else []
            if any(_polygon_contains(poly,target) for poly in polys):
                name=(f.get('properties') or {}).get('planning_area')
                hit=bundle.areas[bundle.areas.planning_area.astype(str).str.upper()==str(name).upper()]
                if len(hit):return hit.iloc[0],'inside planning-area polygon'
    return _closest_area(bundle.areas,site),'nearest planning-area centroid (approx.)'


def _load_demographics() -> pd.DataFrame:
    """Optional official population data, NEVER generated from vegetation proxies."""
    if not CENSUS.exists():return pd.DataFrame()
    d=pd.read_csv(CENSUS)
    required={'planning_area','year','resident_population','resident_households','source'}
    if not required.issubset(d):
        raise ValueError('Demographics CSV requires planning_area,year,resident_population,resident_households,source')
    d=d.copy()
    d['planning_area']=d.planning_area.astype(str).str.strip().str.upper()
    if d.planning_area.duplicated().any():
        raise ValueError('Only one census row per planning area; choose one reporting year')
    for col in ('resident_population','resident_households'):
        d[col]=pd.to_numeric(d[col],errors='coerce')
        if (d[col].dropna()<0).any():raise ValueError(f'Demographic values in {col} must be nonnegative')
    if d.source.isna().any() or d.source.astype(str).str.strip().eq('').any():
        raise ValueError('Every demographic row must identify its primary source')
    return d.set_index('planning_area')


def site_profiles(bundle, layout: list[dict]):
    d=_load_demographics()
    rows=[]
    for site in layout:
        area,method=_area_for_point(bundle,site)
        p=str(area.planning_area).upper()
        row={
            'site_name':str(site.get('name') or site.get('site_id') or 'Candidate site'),
            'planning_area':p,
            'region':str(area.get('region','n/a')),
            'pwc_sector':str(area.get('pwc_sector','n/a')),
            'locate_method':method,
            'area_km2':_flt(area.get('area_km2')),
            'tree_count':_flt(area.get('n_trees')),
            'tree_cover_pct':_flt(area.get('tree_pct')),
            'built_cover_pct':_flt(area.get('built_pct')),
            'vegetation_proxy_t':_flt(area.get('estimated_t')),
            'resident_population':None,
            'resident_households':None,
            'population_year':None,
            'population_source':None,
        }
        if p in d.index:
            cen=d.loc[p]
            row.update(resident_population=_flt(cen.resident_population),
                       resident_households=_flt(cen.resident_households),
                       population_year=str(cen.year), population_source=str(cen.source))
        rows.append(row)
    return rows


def _flt(x):
    try:
        v=float(x)
        return v if math.isfinite(v) else None
    except (TypeError,ValueError):return None


def _serif(size=18,bold=False):
    candidates=[
        '/usr/share/fonts/truetype/croscore/Tinos-Bold.ttf' if bold else '/usr/share/fonts/truetype/croscore/Tinos-Regular.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf' if bold else '/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf',
        str(Path('C:/Windows/Fonts/timesbd.ttf' if bold else 'C:/Windows/Fonts/times.ttf')),
    ]
    for f in candidates:
        try:return ImageFont.truetype(f,size)
        except OSError:continue
    return ImageFont.load_default()


def _crop_print(image: Image.Image) -> bytes:
    """Make the on-screen dark 3D map legible in a grayscale printed report."""
    im=ImageOps.exif_transpose(image).convert('RGB')
    im.thumbnail((1600,1000),Image.Resampling.LANCZOS)
    gray=ImageOps.grayscale(im)
    # MapLibre dark map: invert so dark terrain becomes a white page with dark roads/text.
    if np.asarray(gray.resize((30,20))).mean()<125:
        gray=ImageOps.invert(gray)
    gray=ImageEnhance.Contrast(gray).enhance(1.20)
    bio=io.BytesIO();gray.save(bio,format='PNG',optimize=True)
    return bio.getvalue()


def parse_browser_capture(data_uri: str | None) -> bytes | None:
    """A small validated PNG/JPEG capture, with an upper payload limit."""
    if not data_uri:return None
    if not isinstance(data_uri,str) or len(data_uri)>4_000_000:
        raise ValueError('Site map capture exceeds the 4 MB safety limit')
    import re
    m=re.fullmatch(r'data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)',data_uri)
    if not m:raise ValueError('Map capture must be a base64 PNG or JPEG data URI')
    raw=base64.b64decode(m.group(2),validate=True)
    if len(raw)>3_000_000:raise ValueError('Map capture must be below 3 MB')
    im=Image.open(io.BytesIO(raw))
    if im.width>4500 or im.height>4500 or im.width<150 or im.height<150:
        raise ValueError('Map screenshot has unsupported dimensions')
    return _crop_print(im)


def isometric_site_view(bundle, layout: list[dict]) -> bytes:
    """Grayscale source-labelled *schematic* based on project area coordinates.

    3D columns encode area proxy tonnes and do not claim true geography elevation.
    """
    W,H=1400,770
    im=Image.new('RGB',(W,H),'white'); dr=ImageDraw.Draw(im)
    head=_serif(28,True);small=_serif(19);tiny=_serif(16)
    areas=bundle.areas.copy()
    sites=layout or []
    lat0=float(np.mean([s['lat'] for s in sites])) if sites else 1.34
    lon0=float(np.mean([s['lon'] for s in sites])) if sites else 103.82
    # closest local districts by geographic centroid, rather than largest across Singapore
    a=areas.assign(dist2=(areas.longitude-lon0)**2 * (math.cos(math.radians(lat0))**2)+(areas.latitude-lat0)**2)
    a=a.nsmallest(16,'dist2')
    radius=max(2.5,math.sqrt(max(float(a.dist2.max()),.00001))*111*1.5)
    def project(x,y,z=0):
        # x,y in km relative to candidate site; z dimension = modelled supply (relative)
        sx=695 + (x-y)*31
        sy=445 + (x+y)*13 - z
        return sx,sy
    # schematic isometric plane
    plane=[project(-radius,-radius),project(radius,-radius),project(radius,radius),project(-radius,radius)]
    dr.polygon(plane,fill=(248,248,248),outline=(85,85,85),width=3)
    for k in range(-4,5):
        f=k/4*radius
        dr.line([project(f,-radius),project(f,radius)],fill=(205,205,205),width=1)
        dr.line([project(-radius,f),project(radius,f)],fill=(205,205,205),width=1)
    dr.text((55,38),'SELECTED SITE: 3D SPATIAL MODEL',fill='black',font=head)
    dr.text((55,87),'Greyscale analytical visualization | Not a photograph or surveyed building model',fill=(55,55,55),font=small)
    maxw=max(1.0,float(a.estimated_t.max()))
    elements=[]
    for r in a.itertuples():
        x=(float(r.longitude)-lon0)*111.3*math.cos(math.radians(lat0))
        y=(float(r.latitude)-lat0)*110.6
        h=20+110*float(r.estimated_t)/maxw
        elements.append((x+y,x,y,h,str(r.planning_area).title(),False))
    # draw back-to-front
    for _,x,y,h,lab,_ in sorted(elements,reverse=True):
        cx,cy=project(x,y)
        size=18
        c1=(cx-size,cy);c2=(cx,cy-size*.47);c3=(cx+size,cy);c4=(cx,cy+size*.47)
        dr.polygon([(c1[0],c1[1]-h),(c2[0],c2[1]-h),(c3[0],c3[1]-h),(c4[0],c4[1]-h)],fill=(80,80,80),outline='black')
        dr.polygon([(c1[0],c1[1]-h),(c4[0],c4[1]-h),c4,c1],fill=(205,205,205),outline=(80,80,80))
        dr.polygon([(c4[0],c4[1]-h),(c3[0],c3[1]-h),c3,c4],fill=(150,150,150),outline=(80,80,80))
    for s in sites:
        x=(float(s['lon'])-lon0)*111.3*math.cos(math.radians(lat0))
        y=(float(s['lat'])-lat0)*110.6
        cx,cy=project(x,y)
        dr.ellipse((cx-13,cy-13,cx+13,cy+13),fill='black',outline='white',width=3)
        dr.line((cx,cy,cx,cy-155),fill='black',width=4)
        dr.ellipse((cx-11,cy-167,cx+11,cy-145),fill='white',outline='black',width=4)
        dr.text((cx+20,cy-170),str(s.get('site_id') or 'SITE'),fill='black',font=head,stroke_width=3,stroke_fill='white')
    dr.text((55,681),'EXTRUSION = MODELLED WASTE PROXY; HEIGHT DOES NOT REPRESENT PHYSICAL ELEVATION',fill='black',font=tiny)
    dr.text((55,712),'Source: BioTwin planning-area estimates and candidate site coordinates (URA / NParks proxies)',fill=(70,70,70),font=tiny)
    out=io.BytesIO();im.save(out,format='PNG',optimize=True)
    return out.getvalue()
