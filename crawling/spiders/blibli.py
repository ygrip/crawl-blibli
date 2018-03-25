import scrapy
from collections import defaultdict
from scrapy.selector import Selector
from scrapy.http import HtmlResponse
import json
import re
import os
import urllib.parse
import sys


class BliBliSpider(scrapy.Spider):
    name = "blibli"
    PAGE_LIMIT = 10
    def start_requests(self):
        urls = [
            'https://www.blibli.com/coffee-maker/54650',
            'https://www.blibli.com/televisi/54650',
            'https://www.blibli.com/perangkat-kecantikan/54650',
            'https://www.blibli.com/perlengkapan-elektronik-dapur/54650',
            'https://www.blibli.com/microwave-dan-oven/54650',
            'https://www.blibli.com/pendingin-ruangan/54650',
            'https://www.blibli.com/elektronik-dapur/54650',
            'https://www.blibli.com/home-appliances/54650',
            'https://www.blibli.com/multimedia/53270',
            'https://www.blibli.com/media-penyimpanan/53270',
            'https://www.blibli.com/aksesoris-komputer/53270',
            'https://www.blibli.com/peralatan-gaming/53270',
            'https://www.blibli.com/scanner/53270',
            'https://www.blibli.com/printer-refill/53270',
            'https://www.blibli.com/wearable-gadget/54593',
            'https://www.blibli.com/handphone/54593',
            'https://www.blibli.com/aksesoris-handphone-tablet/54593',
            'https://www.blibli.com/tablet/54593',
        ]
        for url in urls:
            # proxy_meta = "http://yunazgilang@it.student.pens.ac.id:mIsery@230196@proxy3.pens.ac.id:3128"
            proxy_meta = ''
            request = scrapy.Request(url=url, callback=self.parse)
            request.meta['proxy'] = proxy_meta
            request.meta['pages'] = 0
            yield request

    def parse_page(self, response):
        filename = response.meta['filepath']
        product = []
        cleanr = re.compile('<.*?>')
        product_details = defaultdict(list)
        selector = scrapy.Selector(text=response.body, type="html")
        product_details["brand"] = response.css('div.brand-garansi span.brand-info a::text').extract_first()
        product_details["brand_image"] = response.css('div.brand-logo-block section.brand-border img::attr(src)').extract_first()
        product_details["produk_url"] = response.meta['url_product']
        product_details["brand_link"] = response.css('div.brand-garansi span.brand-info a::attr(href)').extract_first()
        product_details["title"] = response.css('h1.product-name::text').extract_first()
        product_details["category"] = response.xpath('//*[@id="bread-scrum"]/a/text()').extract()
        product_details["harga_awal"] = selector.xpath('//*[@id="strikeThroughPrice"]/text()').extract_first()
        product_details["harga_akhir"] = response.xpath('//*[@id="priceDisplay"]/text()').extract_first()
        product_details["diskon"] = response.css('span.discount-price span b::text').extract_first()
        product_details["produk_feat"] = response.css('div.large-16.medium-16.small-16.columns.product-usp ul li::text').extract()
        product_details["produk_desc"] = re.sub(cleanr, '', selector.xpath('//*[@id="productinfo"]').re_first(re.compile('.+', re.DOTALL)))
        product_details["produk_spec"] = re.sub(cleanr, '', selector.xpath('//*[@id="productdetail"]').re_first(re.compile('.+', re.DOTALL)))
        product_details["produk_sku"] = response.xpath('//ul[@class="sku-block"]/li[contains(label, "SKU Number")]/span/text()').extract_first()
        product_details["produk_code"] = response.xpath('//ul[@class="sku-block"]/li[contains(label, "Product Code")]/span/text()').extract_first()
        product_details["produk_ean"] = response.xpath('//ul[@class="sku-block"]/li[contains(label, "EAN Code")]/span/text()').extract_first()
        product_details["url_images"] = response.css('ul#list-image li a::attr(data-image)').extract()
        product = product_details
        a = []
        if not os.path.isfile(filename):
            a.append(product)
            with open(filename, mode='w',encoding='utf-8') as f:
                f.write(json.dumps(a, indent=2))
        else:
            with open(filename) as feedsjson:
                feeds = json.load(feedsjson)
            feeds.append(product)
            with open(filename, mode='w',encoding='utf-8') as f:
                f.write(json.dumps(feeds, indent=2))
        self.logger.info('Processed : %s' % product_details["title"])

    def parse(self, response):
        count_pages = response.meta['pages']
        if count_pages < self.PAGE_LIMIT:
            page = response.url.split("/")[-2]
            filename = 'output/blibli/produk-%s.json' % page
            list_url_product = response.css('a.single-product::attr(href)').extract()
            if list_url_product is not None:
                for url_product in list_url_product:                    
                    url = url_product
                    url_product = "http://192.168.99.100:8050/render.html?" + urllib.parse.urlencode({ 'url' : url_product})
                    product_request = scrapy.Request(url=url_product,callback=self.parse_page)
                    product_request.meta['proxy'] = ''
                    product_request.meta['dont_obey_robotstxt'] = True
                    product_request.meta['url_product'] = url
                    product_request.meta['filepath'] = filename
                    yield product_request
            self.log('Saved file %s' % filename)
            href = response.css('div.paging a#next::attr(onclick)').extract_first()
            if href is not None:
                count_pages = count_pages + 1
                href = re.findall("'([^' ]+)'",href)
                next_page = response.urljoin(href[0])                
                request = scrapy.Request(url=next_page, callback=self.parse)
                request.meta['proxy'] = response.meta['proxy']
                request.meta['pages'] = count_pages
                yield request