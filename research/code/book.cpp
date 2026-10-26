#include <algorithm>
#include <array>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <fcntl.h>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>
#include <omp.h>
struct Npy {
 int fd; size_t bytes,offset;void*mem;std::vector<size_t> shape;
 Npy(const std::string&p,bool write=false){fd=::open(p.c_str(),write?O_RDWR:O_RDONLY);if(fd<0)throw std::runtime_error("open "+p);struct stat st;fstat(fd,&st);bytes=st.st_size;mem=mmap(0,bytes,write?(PROT_READ|PROT_WRITE):PROT_READ,MAP_SHARED,fd,0);if(mem==MAP_FAILED)throw std::runtime_error("mmap");auto b=(unsigned char*)mem;int len=b[6]==1?(b[8]|b[9]<<8):(b[8]|b[9]<<8|b[10]<<16|b[11]<<24);offset=(b[6]==1?10:12)+len;std::string h((char*)mem+(b[6]==1?10:12),len);auto a=h.find("(",h.find("shape")),z=h.find(")",a);std::string dim=h.substr(a+1,z-a-1);std::replace(dim.begin(),dim.end(),',',' ');std::istringstream ss(dim);size_t v;while(ss>>v)shape.push_back(v);}
 ~Npy(){munmap(mem,bytes);close(fd);}template<class T>T*data(){return (T*)((char*)mem+offset);}
};
struct Lot {int sym,sleeve,entry,due;double opening,mark;std::array<double,4> q;};
struct Metric {bool ready=false;int n=0;int64_t start=0,end=0;double first=0,last=0,peak=0,dd=0,s=0,ss=0;
 void add(int64_t day,double value){if(!ready){ready=true;first=last=peak=value;start=end=day;return;}double r=value/last-1;s+=r;ss+=r*r;n++;last=value;end=day;peak=std::max(peak,value);dd=std::min(dd,value/peak-1);}
 void write(double*x){if(!ready||end<=start){for(int j=0;j<6;j++)x[j]=NAN;return;}double vol=n>1?std::sqrt(std::max(0.,(ss-s*s/n)/(n-1))*252):0.;x[0]=std::pow(last/first,365.25/double(end-start))-1;x[1]=last/first-1;x[2]=dd;x[3]=vol;x[4]=vol>0?(s/n*252)/vol:0.;x[5]=last/first;}
};
int main(int argc,char**argv){
 if(argc!=11){std::cerr<<"book DATA PICKS OUT FIRST LAST FEES PHASE DEV_INDEX MATCH_INDEX NAV_OR_DASH\n";return 2;}
 std::string d=argv[1];Npy op(d+"/open.npy"),cl(d+"/adj.npy"),vo(d+"/volume.npy"),days(d+"/calendar_days.npy"),pick(argv[2]),out(argv[3],true);
 int first=std::stoi(argv[4]),last=std::stoi(argv[5]),phase=std::stoi(argv[7]),dev=std::stoi(argv[8]),match=std::stoi(argv[9]);std::vector<double>fees;std::string tok;std::istringstream stream(argv[6]);while(std::getline(stream,tok,','))fees.push_back(std::stod(tok));int F=fees.size();if(F>4)return 2;
 Npy*path=std::string(argv[10])=="-"?nullptr:new Npy(argv[10],true);
 int T=op.shape[0],S=op.shape[1],M=pick.shape[0],D=pick.shape[1],J=T-first;auto O=op.data<double>(),C=cl.data<double>(),V=vo.data<double>(),A=out.data<double>();auto DS=days.data<int64_t>();auto P=pick.data<int16_t>();double*N=path?path->data<double>():nullptr;if(first<300)throw std::runtime_error("first must preserve calendar anchor >=300");
 if(D!=last-first+1||pick.shape[2]!=5||out.shape!=std::vector<size_t>({6,(size_t)M,(size_t)F,64}))throw std::runtime_error("shape mismatch");
 #pragma omp parallel for schedule(dynamic,1)
 for(int task=0;task<6*M;task++){
  int mode=task/M,m=task%M,K=mode==5?1:mode+1,cap=mode==5?5:K;
  std::array<std::array<double,4>,5>cash{};if(mode==5){for(auto&x:cash)x.fill(.2);}else cash[0].fill(1.);
  std::vector<Lot>lots;lots.reserve(5);std::array<std::array<double,46>,4>st{};Metric met[4][3];
  for(int f=0;f<F;f++){met[f][0].add(DS[first],1.);if(first<=dev)met[f][1].add(DS[first],1.);if(first>=match)met[f][2].add(DS[first],1.);st[f][14]=1.;if(N)N[((size_t)task*J)*F+f]=1.;}
  for(int t=first+1;t<T;t++){
   size_t keep=0;
   for(auto p:lots){double px=O[(size_t)t*S+p.sym];if(t>=p.due&&std::isfinite(px)&&px>0){
    for(int f=0;f<F;f++){double proceeds=p.q[f]*px;cash[p.sleeve][f]+=proceeds*(1-fees[f]);double r=px/p.opening*(1-fees[f])/(1+fees[f])-1.;st[f][1]++;st[f][2]+=r>0;st[f][3]+=r;st[f][4]+=t>p.due;st[f][9]+=t-p.entry;st[f][10]=std::max(st[f][10],double(t-p.entry));st[f][16]+=proceeds*fees[f];}
   }else lots[keep++]=p;}lots.resize(keep);
   int signal=t-1;
   bool scheduled=signal<=last&&(mode==5||((signal-300)%5)==phase);
   if(scheduled){int sleeve=mode==5?(signal-300)%5:0;bool blocked=false;for(auto&p:lots)if(mode!=5||p.sleeve==sleeve)blocked=true;
    if(blocked){for(int f=0;f<F;f++)st[f][18]++;}
    else{auto budget=cash[sleeve];cash[sleeve].fill(0.);for(int f=0;f<F;f++)st[f][17]++;
     for(int k=0;k<K;k++){int sym=P[((size_t)m*D+(signal-first))*5+k];double px=sym<S?O[(size_t)t*S+sym]:NAN;
      if(!std::isfinite(px)||px<=0){for(int f=0;f<F;f++){cash[sleeve][f]+=budget[f]/K;st[f][5]++;}continue;}
      Lot p;p.sym=sym;p.sleeve=sleeve;p.entry=t;p.due=t+5;p.opening=p.mark=px;p.q.fill(0.);
      for(int f=0;f<F;f++){p.q[f]=budget[f]/K/(1+fees[f])/px;st[f][0]++;st[f][16]+=p.q[f]*px*fees[f];}lots.push_back(p);
     }
    }
   }
   if((int)lots.size()>cap)throw std::runtime_error("position cap exceeded");
   int distinct=0;for(size_t i=0;i<lots.size();i++){bool earlier=false;for(size_t j=0;j<i;j++)if(lots[j].sym==lots[i].sym)earlier=true;distinct+=!earlier;}
   std::array<double,4>value{},cashsum{};for(int s=0;s<5;s++)for(int f=0;f<F;f++)cashsum[f]+=cash[s][f];value=cashsum;
   for(auto&p:lots){double mark=C[(size_t)t*S+p.sym];bool observed=std::isfinite(mark)&&mark>0&&V[(size_t)t*S+p.sym]>0;if(observed)p.mark=mark;else for(int f=0;f<F;f++)st[f][11]++;for(int f=0;f<F;f++)value[f]+=p.q[f]*p.mark;}
   for(int f=0;f<F;f++){if(!std::isfinite(value[f])||value[f]<=0||cashsum[f]<-1e-10)throw std::runtime_error("invalid funding");
    st[f][6]=std::max(st[f][6],double(lots.size()));st[f][13]=std::max(st[f][13],double(distinct));st[f][14]=std::min(st[f][14],cashsum[f]);st[f][15]=std::max(st[f][15],1-cashsum[f]/value[f]);
    met[f][0].add(DS[t],value[f]);if(t<=dev)met[f][1].add(DS[t],value[f]);if(t>=match)met[f][2].add(DS[t],value[f]);if(N)N[(((size_t)task*J)+(t-first))*F+f]=value[f];
   }
  }
  for(int f=0;f<F;f++){st[f][7]=lots.size();for(auto&p:lots)st[f][8]+=p.q[f]*p.mark;double*x=A+((size_t)task*F+f)*64;for(int period=0;period<3;period++)met[f][period].write(x+period*6);for(int q=0;q<46;q++)x[18+q]=st[f][q];}
 }
 delete path;return 0;
}
