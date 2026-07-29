package com.ssafy.eyesonu.missingcase.domain;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class ReporterRecord {
	private Long id;
	private String name;
	private String phone;
	private String email;
	private String relation;
}
