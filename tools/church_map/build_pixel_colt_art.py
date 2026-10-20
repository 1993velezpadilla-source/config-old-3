#!/usr/bin/env python3
"""Original 2D ink-and-pixel FPS Colt M1911 proof sprites (not copied game art).

Six full-screen RGBA frames, 1536x1024, supplied as *source-driven* SVG art
rasterized in CI with CairoSVG. Preserve linework; NEVER crop to 64px HUD icons.
Game activation awaits weapon-frame timing gauntlet (do not overwrite working
3D M1911 viewmodel until that gate is proven).
"""
import argparse
import io
import json
from pathlib import Path
import cairosvg
from PIL import Image,ImageStat

DEFS = r"""
<defs>
 <linearGradient id="steel" x1="0" y1="0" x2="1" y2="1">
  <stop stop-color="#7e8890"/><stop offset=".20" stop-color="#475562"/>
  <stop offset=".47" stop-color="#222a34"/><stop offset=".73" stop-color="#414853"/>
  <stop offset="1" stop-color="#12171f"/>
 </linearGradient>
 <linearGradient id="steelTop" x1="0" y1="0" x2=".7" y2="1">
  <stop stop-color="#a8a9a5"/><stop offset=".20" stop-color="#69737a"/>
  <stop offset=".68" stop-color="#2f3438"/><stop offset="1" stop-color="#10161b"/>
 </linearGradient>
 <linearGradient id="glove" x1="0" y1="0" x2="1" y2="1">
  <stop stop-color="#4b3932"/><stop offset=".45" stop-color="#201b1c"/>
  <stop offset="1" stop-color="#090c12"/>
 </linearGradient>
 <linearGradient id="grip" x1="0" y1="0" x2="1" y2="1">
  <stop stop-color="#8b5941"/><stop offset=".42" stop-color="#502f28"/>
  <stop offset="1" stop-color="#241718"/>
 </linearGradient>
 <radialGradient id="flash">
  <stop stop-color="#fff4ce"/><stop offset=".20" stop-color="#ffe39a"/>
  <stop offset=".49" stop-color="#ee9d45"/><stop offset="1" stop-color="#c24e1900"/>
 </radialGradient>
</defs>
"""

# 2.5D locked-perspective handgun, colored with restrained edge hatching and
# thick irregular ink contours inspired by illustrated pulp-horror comics.
HIP = r"""
<g stroke="#101015" stroke-width="7" stroke-linejoin="round" stroke-linecap="round">
 <path d="M986 798 L1095 1024 L1327 1024 L1209 815 L1138 738Z" fill="#14151b" stroke="#050609" stroke-width="18"/>
 <path d="M986 763 Q966 701 1020 666 Q1090 641 1135 702 L1250 855 L1218 1024 L1051 1015Z" fill="url(#glove)" stroke-width="12"/>
 <path d="M995 728 Q953 692 944 638 L992 593 L1053 627 L1084 682 Q1060 739 995 728Z" fill="#675048"/>
 <path d="M1031 740 Q986 744 965 770 M1085 765 Q1043 775 1024 812 M1134 804 Q1103 821 1098 863" fill="none" stroke="#695347" stroke-width="5"/>
 <!-- frame rails -->
 <path d="M826 535 L1013 646 L1066 718 L1018 753 L906 671 L856 633 L790 601Z" fill="#20232a"/>
 <path d="M892 647 L1008 723 L1002 836 L943 883 L856 736Z" fill="url(#grip)" stroke-width="13"/>
 <path d="M909 696 L972 747 L962 826 L929 840 L879 740Z" fill="#593b32"/>
 <path d="M908 724 L963 769 M899 743 L957 789 M919 764 L952 801 M923 787 L949 818" fill="none" stroke="#1c1b1a" stroke-width="4"/>
 <circle cx="946" cy="756" r="8" fill="#a68c71" stroke-width="3"/><circle cx="948" cy="818" r="7" fill="#a68c71" stroke-width="3"/>
 <path d="M864 643 Q828 672 839 710 Q862 736 892 712 L917 673" fill="none" stroke="#161c22" stroke-width="20"/>
 <path d="M888 675 Q871 690 868 707" fill="none" stroke="#a08468" stroke-width="8"/>
 <!-- muzzle far perspective -->
 <path d="M690 384 L770 385 L825 436 L783 495 L711 469 L657 433Z" fill="url(#steelTop)" stroke-width="12"/>
 <ellipse cx="684" cy="414" rx="39" ry="28" transform="rotate(18 684 414)" fill="#101216" stroke="#a1a2a0" stroke-width="9"/>
 <ellipse cx="688" cy="416" rx="15" ry="12" transform="rotate(18 688 416)" fill="#040507" stroke-width="2"/>
 <!-- upper slide, bevel and serrations -->
 <path d="M747 369 L961 520 L1045 630 L1010 662 L814 525 L689 451Z" fill="url(#steelTop)" stroke-width="14"/>
 <path d="M767 421 L963 555 L1013 633 L976 647 L790 518 L712 455Z" fill="url(#steel)" stroke-width="8"/>
 <path d="M766 391 L950 516 L1012 603" fill="none" stroke="#c4b6a3" stroke-width="5"/>
 <path d="M777 449 L931 550 M793 470 L944 568 M812 493 L953 583" fill="none" stroke="#87919a" stroke-width="3"/>
 <!-- ejection port -->
 <path d="M894 508 L957 547 L984 583 L961 591 L890 546Z" fill="#090c11" stroke="#76838a" stroke-width="6"/>
 <path d="M916 527 L951 552 L961 572 L933 560Z" fill="#ae8760" stroke="#3d3025" stroke-width="2"/>
 <!-- rear serrations -->
 <path d="M980 581 L1001 613 M972 594 L989 626 M962 605 L977 637" fill="none" stroke="#090b0d" stroke-width="7"/>
 <!-- sights -->
 <path d="M768 367 L766 341 L786 348 L792 380Z" fill="#272b30" stroke-width="5"/>
 <path d="M983 535 L989 502 L1009 514 L1014 548Z" fill="#21252c" stroke-width="5"/>
 <path d="M782 360 L783 351" stroke="#e5cda2" stroke-width="4"/>
 <!-- trigger and safety -->
 <path d="M935 657 Q932 670 926 684" fill="none" stroke="#d4aa7a" stroke-width="6"/>
 <circle cx="992" cy="666" r="7" fill="#d9c1a4" stroke-width="3"/>
 <!-- index finger -->
 <path d="M1059 676 Q1009 657 978 675 Q947 692 936 713 Q951 744 985 737 Q1010 718 1052 717" fill="url(#glove)" stroke-width="12"/>
 <path d="M967 711 Q1008 701 1043 713" stroke="#7c6659" stroke-width="4" fill="none"/>
 <!-- ink scratch details, intentionally irregular not glossy CAD -->
 <path d="M819 426 L840 436 M855 451 L861 458 M846 520 L865 530 M919 600 L925 609" fill="none" stroke="#d5c8a2" stroke-width="3"/>
</g>
"""

ADS=r"""
<g stroke="#0c0e11" stroke-width="9" stroke-linejoin="round" stroke-linecap="round">
 <!-- arms frame pistol from left and right; symmetric iron-sight geometry -->
 <path d="M506 1024 L589 751 Q640 698 702 738 L730 841 L713 1024Z" fill="url(#glove)" stroke-width="18"/>
 <path d="M1007 1024 L947 751 Q881 698 836 747 L808 840 L825 1024Z" fill="url(#glove)" stroke-width="18"/>
 <path d="M649 741 Q652 711 688 684 L746 709 L755 807 L685 860Z" fill="#675044"/>
 <path d="M893 747 Q894 716 849 679 L800 713 L796 804 L865 859Z" fill="#695249"/>
 <path d="M695 697 L842 697 L864 1000 L672 1000Z" fill="url(#grip)" stroke-width="16"/>
 <path d="M713 747 L820 747 L826 954 L708 954Z" fill="#44332b" stroke-width="5"/>
 <path d="M722 782 L809 782 M724 810 L813 810 M725 839 L814 839 M728 868 L816 868" fill="none" stroke="#221e20" stroke-width="4"/>
 <path d="M700 582 L837 582 L869 728 L680 728Z" fill="url(#steel)" stroke-width="17"/>
 <path d="M730 475 L806 475 L828 616 L704 616Z" fill="url(#steelTop)" stroke-width="12"/>
 <path d="M719 528 L815 528 M717 555 L820 555" fill="none" stroke="#9a9590" stroke-width="4"/>
 <path d="M697 494 L719 494 L722 456 L738 456 L738 502 L799 502 L799 457 L817 457 L824 495 L843 495 L834 535 L701 535Z" fill="#171c22" stroke-width="8"/>
 <path d="M749 486 L788 486 L788 493 L749 493Z" fill="#d5c6a0" stroke-width="3"/>
 <path d="M729 596 L808 596" stroke="#161c23" stroke-width="9"/>
 <path d="M705 656 L833 656" stroke="#13151c" stroke-width="6"/>
 <circle cx="771" cy="712" r="8" fill="#ae9582" stroke-width="2"/>
 <path d="M704 755 L733 755 M806 756 L833 756" stroke="#b1aaa1" stroke-width="4"/>
 <path d="M678 774 Q645 737 615 789 L662 850 L701 823 M854 821 L897 787 Q913 743 935 793 L889 857" fill="url(#glove)" stroke-width="12"/>
</g>
"""

def svg(frame:str)->str:
    # Presentation FPS sprite dimensions fixed at 1536x1024; transparency and
    # full-frame hand/weapon geometry are intentionally not cropped or resized.
    ads=frame.startswith("ads")
    art=ADS if ads else HIP
    if frame=="hip_fire":
        art='<g transform="translate(-8 21) rotate(-2 800 650)">'+art+'</g>'
    elif frame=="hip_reload":
        art='<g transform="rotate(24 930 670) translate(105 -70)">'+art+'</g>'
    elif frame=="hip_reload_empty":
        art='<g transform="rotate(27 930 670) translate(110 -50)">'+art+'</g>'
        art+='<g stroke="#121317" stroke-width="10"><path d="M1095 700 L1144 730 L1250 938 L1197 963Z" fill="#464850"/><path d="M1110 731 L1191 902" stroke="#82888a" stroke-width="6"/></g>'
    if frame.endswith("_fire"):
        art+='<g><ellipse cx="684" cy="391" rx="135" ry="150" fill="url(#flash)"/><path d="M680 252 L711 342 L791 304 L741 384 L827 430 L724 440 L691 560 L653 458 L554 492 L619 407 L558 337 L650 370Z" fill="#f6c36b" opacity=".91"/><path d="M679 332 L699 388 L741 357 L715 416 L758 440 L695 437 L672 489 L660 435 L613 437 L656 403 L634 368Z" fill="#fff6d1"/></g>'
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1536" height="1024" viewBox="0 0 1536 1024">'
            +DEFS+art+'</svg>')

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("out",type=Path)
    args=ap.parse_args()
    args.out.mkdir(parents=True,exist_ok=True)
    frames=("hip_idle","hip_fire","hip_reload","hip_reload_empty","ads_idle","ads_fire")
    report={"project":"XZIEL_STORYBOOK_COLT_M1911","style":"original 2D ink-comic with pixel-edge hard contours",
            "source":"authorial SVG, not copyrighted game sprite rip",
            "status":"ART_ONLY_NOT_YET_ACTIVATED_IN_GAME","frames":{}}
    for frame in frames:
        rendered=cairosvg.svg2png(bytestring=svg(frame).encode("utf-8"),output_width=1536,output_height=1024)
        im=Image.open(io.BytesIO(rendered)).convert("RGBA")
        bbox=im.getchannel("A").getbbox()
        if not bbox or bbox[2]-bbox[0]<140 or bbox[3]-bbox[1]<350:
            raise RuntimeError(f"{frame}: cropped/tiny art invalid {bbox}")
        dst=args.out/(frame+".png")
        dst.write_bytes(rendered)
        if dst.stat().st_size<22000:
            raise RuntimeError(f"{frame}: image is empty/too small")
        report["frames"][frame]={"dimensions":[1536,1024],"alpha_bounds":list(bbox),
                                 "bytes":dst.stat().st_size}
        print("XZIEL_AUTHORED_2D_COLT_FULLRES",frame,bbox,flush=True)
    (args.out/"manifest.json").write_text(json.dumps(report,indent=2)+"\n")
    print("XZIEL_SIX_2D_COLT_FULLRES_PNG_ART_SOURCE_GREEN",flush=True)

if __name__=="__main__":
    main()
